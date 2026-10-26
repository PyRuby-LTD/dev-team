"""Checkout ownership and dispatch ordering with real repositories."""
import threading
import unittest
from unittest.mock import patch

from devteam import git
from devteam.runner import Waiting, StepFailed, sync
from tests import test_merged


class CheckoutQueue(unittest.TestCase):
    def setUp(self):
        test_merged.Merged.setUp(self)
        self.runner.max_runs = 20
        self.at(self.item, 'accept')
        self.runner.take_checkout(self.other)
        self.runner.check = self.check
        self.runner.engine = self.engine
        self.calls = []

    no_engine = test_merged.Merged.no_engine

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

    def test_queued_holder_runs_before_earlier_item_for_sync_and_check(self):
        for step in ('sync', 'verify'):
            with self.subTest(step=step):
                self.at(self.item, 'implement')
                self.at(self.other, step)
                git.must(self.product, 'switch', '-q', f'devteam/{self.other.id}')
                self.calls.clear()
                self.messages.clear()
                self.assertEqual(1, self.dispatch_in_claim_order())
                self.assertEqual(f'devteam/{self.other.id}', git.current_branch(self.product))
                self.assertEqual('implement', self.repo.scan().valid[self.item.id].metadata['step'])
                self.assertFalse(any(f'waiting for {self.item.id}' in message for message in self.messages))
                if step == 'sync':
                    self.assertEqual('verify', self.repo.scan().valid[self.other.id].metadata['step'])
                    self.assertEqual(1, self.dispatch_in_claim_order())
                self.assertEqual('review', self.repo.scan().valid[self.other.id].metadata['step'])
                self.assertEqual(1, self.dispatch_in_claim_order())
                self.assertEqual('accept', self.repo.scan().valid[self.other.id].metadata['step'])
                self.assertTrue(all(branch == f'devteam/{self.other.id}' for _, branch in self.calls))
                self.assertEqual(1, self.dispatch_in_claim_order())
                self.assertEqual(f'devteam/{self.item.id}', git.current_branch(self.product))
                self.assertEqual('test', self.repo.scan().valid[self.item.id].metadata['step'])
                self.at(self.item, 'accept')

    def test_failed_holder_waits_clean_or_dirty_and_can_retry(self):
        for dirty in (False, True):
            for waiting_step in ('implement', 'sync'):
                with self.subTest(dirty=dirty, waiting_step=waiting_step):
                    self.at(self.item, 'accept')
                    holder = self.at(self.other, 'test')
                    self.runner.retry(holder.id)
                    self.runner.note_waiting(holder, self.repo.step(holder), 'old waiting reason')

                    def fail(*args):
                        if dirty:
                            (self.product / 'unfinished.txt').write_text('unfinished')
                        return 1, 'failed'

                    self.runner.engine = fail
                    self.assertEqual(1, self.dispatch_in_claim_order())
                    self.assertIn(holder.id, self.runner.failed)
                    self.assertNotIn(holder.id, self.runner.waiting)
                    waiter = self.at(self.item, waiting_step)
                    reason = f'waiting for {holder.id}, which holds the checkout at step test'
                    self.assertEqual(0, self.dispatch_in_claim_order())
                    self.assertEqual(reason, self.runner.waiting[waiter.id])
                    self.assertNotIn(waiter.id, self.runner.failed)
                    # Exercise both entry points as well as the claim guard.
                    for action in (self.runner.take_checkout, lambda record: sync(self.runner, record)):
                        with self.assertRaises(Waiting) as raised:
                            action(waiter)
                        self.assertEqual(reason, str(raised.exception))
                    self.assertEqual(f'devteam/{holder.id}', git.current_branch(self.product))
                    self.runner.retry(holder.id)
                    self.runner.engine = self.engine
                    self.assertEqual(1, self.dispatch_in_claim_order())
                    self.assertEqual('sync', self.repo.scan().valid[holder.id].metadata['step'])
                    self.assertNotIn(holder.id, self.runner.failed)
                    self.assertNotIn(holder.id, self.runner.waiting)
                    self.assertEqual(f'devteam/{holder.id}', git.current_branch(self.product))

    def test_unexpected_failure_clears_previous_wait(self):
        holder = self.at(self.other, 'test')
        self.runner.note_waiting(holder, self.repo.step(holder), 'old waiting reason')

        def fail(*args):
            raise RuntimeError('unexpected engine failure')

        self.runner.engine = fail
        self.assertEqual(1, self.dispatch_in_claim_order())
        self.assertIn(holder.id, self.runner.failed)
        self.assertNotIn(holder.id, self.runner.waiting)

    def test_three_items_serialize_running_and_consecutive_checkout_steps(self):
        third = self.repo.create('story', 'Third', parent=self.item.metadata['parent'])
        for record in (self.item, self.other, third):
            self.at(record, 'implement')
        git.must(self.product, 'switch', '-q', 'main')
        entered, resume = threading.Event(), threading.Event()

        def engine(*args):
            entered.set()
            if not resume.wait(10):
                raise RuntimeError('test did not release engine')
            return self.engine(*args)

        self.runner.engine = engine
        futures = self.runner.dispatch()
        try:
            self.assertTrue(entered.wait(5))
            self.assertEqual(1, len(futures))
            self.assertEqual(f'devteam/{self.item.id}', git.current_branch(self.product))
            self.assertEqual([], self.runner.dispatch())
            for record in (self.other, third):
                self.assertEqual(f'waiting for {self.item.id}, which is using the checkout',
                                 self.runner.waiting[record.id])
        finally:
            resume.set()
            for future in futures:
                future.result(timeout=10)
        self.runner.engine = self.engine
        for expected in ('sync', 'verify', 'review', 'accept'):
            self.assertEqual(1, self.dispatch_in_claim_order())
            self.assertEqual(expected, self.repo.scan().valid[self.item.id].metadata['step'])
            self.assertEqual(f'devteam/{self.item.id}', git.current_branch(self.product))
        self.assertEqual(1, self.dispatch_in_claim_order())
        self.assertEqual(f'devteam/{self.other.id}', git.current_branch(self.product))
        self.assertFalse(git.has_ref(self.product, f'refs/heads/devteam/{third.id}'))

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

    def test_dirty_checkout_without_holder_keeps_existing_guards(self):
        self.at(self.other, 'accept')
        for branch in (f'devteam/{self.item.id}', 'main'):
            with self.subTest(branch=branch):
                git.must(self.product, 'switch', '-q', branch)
                dirty = self.product / 'unfinished.txt'
                dirty.write_text('unfinished')
                with self.assertRaisesRegex(StepFailed, 'uncommitted changes'):
                    sync(self.runner, self.item)
                with self.assertRaisesRegex(Waiting, 'uncommitted changes'):
                    self.runner.take_checkout(self.other)
                self.assertEqual(branch, git.current_branch(self.product))
                dirty.unlink()
