"""Checkout ownership and dispatch ordering with real repositories."""
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from devteam import git
from devteam.backlog import Repository
from devteam.runner import Runner
from tests.test_checkout import IDENTITY


class CheckoutQueue(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, IDENTITY))
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.product = root / 'product'
        subprocess.run(['git', 'init', '-q', '-b', 'main', str(self.product)], check=True)
        (self.product / 'app.txt').write_text('initial\n')
        git.commit_all(self.product, 'initial')
        self.repo = Repository(git.ensure_backlog(self.product))
        epic = self.repo.create('epic', 'Delivery')
        self.item = self.repo.create('story', 'Held', parent=epic.id)
        self.other = self.repo.create('story', 'Next', parent=epic.id)
        self.messages = []
        self.runner = Runner(self.repo, engine=self.engine, report=self.messages.append, checkout=self.product,
                             max_runs=20, check=self.check)
        self.at(self.item, 'implement')
        self.runner.take_checkout(self.item)
        self.at(self.item, 'accept')
        self.runner.take_checkout(self.other)
        self.calls = []

    def at(self, record, step):
        current = self.repo.scan().valid[record.id]
        record.path.write_text(record.path.read_text().replace(
            f'step: {current.metadata["step"]}\n', f'step: {step}\n', 1))
        return self.repo.scan().valid[record.id]

    def check(self, checkout, **kwargs):
        self.calls.append(('check', git.current_branch(checkout)))
        return 0, 'passed'

    def engine(self, role, prompt, cwd, extra_dir, log):
        self.calls.append((role.name, git.current_branch(cwd)))
        return 0, 'TRANSITION: ' + {
            'implementer': 'implemented', 'tester': 'written', 'reviewer': 'approve',
        }[role.name]

    def dispatch_in_claim_order(self):
        # No worker starts until every claim has been attempted. Before BUG-003,
        # the earlier item always reserves the slot and starves the real holder.
        threads = []
        with patch.object(threading.Thread, 'start', lambda thread: threads.append(thread)):
            futures = self.runner.dispatch()
        for thread in threads:
            thread.start()
        for future in futures:
            future.result(timeout=10)
        for thread in threads:
            thread.join(10)
            self.assertFalse(thread.is_alive())
        return len(futures)

    def test_unexpected_failure_clears_previous_wait(self):
        holder = self.at(self.other, 'test')
        self.runner.note_waiting(holder, self.repo.step(holder), 'old waiting reason')

        def fail(*args):
            raise RuntimeError('unexpected engine failure')

        self.runner.engine = fail
        self.assertEqual(1, self.dispatch_in_claim_order())
        self.assertIn(holder.id, self.runner.failed)
        self.assertNotIn(holder.id, self.runner.waiting)

    def test_dependency_wait_precedes_checkout_selection_with_three_items(self):
        third = self.repo.create('story', 'Dependent', parent=self.item.metadata['parent'],
                                 depends_on=[self.other.id])
        for record in (self.item, self.other, third):
            self.at(record, 'implement')
        git.must(self.product, 'switch', '-q', 'main')
        # Even when the dependent is considered first it must not reserve the slot.
        pending = self.runner.pending()
        ordered = sorted(pending, key=lambda pair: pair[0].id != third.id)
        with patch.object(self.runner, 'pending', return_value=ordered):
            self.assertEqual(1, self.dispatch_in_claim_order())
        self.assertIn('to be done', self.runner.waiting[third.id])
        self.assertEqual(f'devteam/{self.item.id}', git.current_branch(self.product))
        self.assertFalse(git.has_ref(self.product, f'refs/heads/devteam/{third.id}'))
        self.at(self.item, 'accept')
        self.assertEqual(1, self.dispatch_in_claim_order())
        self.assertEqual(f'devteam/{self.other.id}', git.current_branch(self.product))
        self.at(self.other, 'done')
        self.assertEqual(1, self.dispatch_in_claim_order())
        self.assertEqual(f'devteam/{third.id}', git.current_branch(self.product))
