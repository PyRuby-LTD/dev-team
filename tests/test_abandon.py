"""Abandon decisions and checkout recovery using real Git repositories."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from devteam import git
from devteam.backlog import InvalidRecord, Repository
from devteam.runner import Runner
from tests.test_checkout import IDENTITY


class Abandon(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        identity = patch.dict(os.environ, IDENTITY)
        identity.start()
        self.addCleanup(identity.stop)
        self.product = Path(self.temp.name) / 'product'
        subprocess.run(['git', 'init', '-q', '-b', 'main', str(self.product)], check=True)
        (self.product / 'app.txt').write_text('initial\n')
        git.commit_all(self.product, 'initial')
        self.base = git.must(self.product, 'rev-parse', 'HEAD')
        self.repo = Repository(git.ensure_backlog(self.product))
        epic = self.repo.create('epic', 'Delivery')
        self.item = self.repo.create('story', 'Abandon', parent=epic.id)
        self.other = self.repo.create('story', 'Next', parent=epic.id)
        self.messages = []
        self.runner = Runner(self.repo, engine=self.no_engine, report=self.messages.append,
                             checkout=self.product)
        self.branch = self.runner.take_checkout(self.item)
        (self.product / 'app.txt').write_text('recoverable work\n')
        git.commit_all(self.product, 'work to preserve')
        self.tip = git.must(self.product, 'rev-parse', 'HEAD')
        # No remote is needed, nor should abandoning attempt any network operation.
        git.must(self.product, 'remote', 'add', 'origin', str(self.product / 'missing.git'))

    def no_engine(self, *args, **kwargs):
        self.fail('abandoning and waiting items must not invoke an engine')

    def at(self, item, step):
        current = self.repo.scan().valid[item.id]
        item.path.write_text(item.path.read_text().replace(
            f"step: {current.metadata['step']}\n", f'step: {step}\n', 1))
        return self.repo.scan().valid[item.id]

    def run_item(self, item):
        current = self.repo.scan().valid[item.id]
        return self.runner.run_item(current, self.repo.step(current))

    def finish(self):
        self.assertTrue(self.run_item(self.item))
        current = self.repo.scan().valid[self.item.id]
        self.assertEqual('abandoned', current.metadata['step'])
        self.assertTrue(self.repo.step(current).terminal)
        self.assertFalse(self.runner.failed)
        self.assertIn('abandoning (harness: abandon): completed -> abandoned', self.messages[-1])
        self.assertEqual(self.tip, git.must(self.product, 'rev-parse', self.branch))
        self.assertEqual(self.base, git.must(self.product, 'rev-parse', 'main'))

    def test_both_customer_steps_abandon_and_only_merged_reaches_done(self):
        for step in ('accept', 'pull-request'):
            with self.subTest(step=step):
                self.at(self.item, step)
                if step == 'accept':
                    with self.assertRaisesRegex(InvalidRecord, 'not a transition'):
                        self.repo.transition(self.item.id, 'accept')
                moved = self.repo.transition(self.item.id, 'abandon')
                self.assertEqual('abandoning', moved.metadata['step'])
                self.assertEqual('abandon', self.repo.step(moved).action)
                self.finish()
                self.assertEqual('main', git.current_branch(self.product))
        steps = self.repo.workflow('default').steps
        self.assertEqual(['merged'], [name for name, step in steps.items()
                                     if 'done' in step.transitions.values()])
        self.assertTrue(steps['abandoned'].terminal)

    def test_clean_checkout_returns_to_base_and_next_item_starts_there(self):
        self.at(self.item, 'abandoning')
        self.finish()
        self.assertEqual('main', git.current_branch(self.product))
        self.assertEqual(f'devteam/{self.other.id}', self.runner.take_checkout(self.other))
        self.assertEqual('main', git.base_of(self.product, f'devteam/{self.other.id}'))
        self.assertEqual(self.base, git.must(self.product, 'rev-parse', 'HEAD'))

    def test_dirty_tracked_and_untracked_fail_hold_checkout_and_retry(self):
        for name in ('app.txt', 'untracked.txt'):
            with self.subTest(name=name):
                git.must(self.product, 'switch', '-q', self.branch)
                self.at(self.item, 'abandoning')
                path = self.product / name
                original = path.read_bytes() if path.exists() else None
                path.write_text('dirty')
                self.assertTrue(self.run_item(self.item))
                self.assertEqual(self.branch, git.current_branch(self.product))
                self.assertEqual('abandoning', self.repo.scan().valid[self.item.id].metadata['step'])
                self.assertIn(f'uncommitted changes on {self.branch}', self.runner.failed[self.item.id])
                self.assertIn('; still at abandoning', self.messages[-1])
                self.assertFalse(self.run_item(self.item))
                self.at(self.other, 'implement')
                self.assertFalse(self.run_item(self.other))
                self.assertIn('holds the checkout at step abandoning', self.runner.waiting[self.other.id])
                if original is None:
                    path.unlink()
                else:
                    path.write_bytes(original)
                self.runner.retry(self.item.id)
                self.finish()

    def test_other_checkout_is_untouched_even_dirty_and_without_recorded_base(self):
        for branch in ('main', 'other', f'devteam/{self.other.id}'):
            for recorded_base in (True, False):
                with self.subTest(branch=branch, recorded_base=recorded_base):
                    git.must(self.product, 'switch', '-q', 'main')
                    if not git.has_ref(self.product, f'refs/heads/{branch}'):
                        git.must(self.product, 'branch', branch)
                    git.must(self.product, 'switch', '-q', branch)
                    if recorded_base:
                        git.must(self.product, 'config', f'branch.{self.branch}.base', 'main')
                    else:
                        git.must(self.product, 'config', '--unset', f'branch.{self.branch}.base')
                    self.at(self.item, 'abandoning')
                    dirty = self.product / 'untracked.txt'
                    dirty.write_text('leave me alone')
                    self.finish()
                    self.assertEqual(branch, git.current_branch(self.product))
                    self.assertEqual('leave me alone', dirty.read_text())
                    dirty.unlink()
                    # A new branch starts here, or the other item resumes its own checkout.
                    self.assertEqual(f'devteam/{self.other.id}', self.runner.take_checkout(self.other))
                    if not branch.startswith('devteam/'):
                        self.assertEqual(branch, git.base_of(self.product, f'devteam/{self.other.id}'))
                    self.assertEqual(self.base, git.must(self.product, 'rev-parse', 'HEAD'))
                    git.must(self.product, 'switch', '-q', 'main')
                    git.must(self.product, 'branch', '-D', f'devteam/{self.other.id}')

    def test_missing_base_fails_on_item_branch_without_switching(self):
        git.must(self.product, 'config', '--unset', f'branch.{self.branch}.base')
        self.at(self.item, 'abandoning')
        self.assertTrue(self.run_item(self.item))
        self.assertIn(f'no base branch is recorded for {self.branch}', self.runner.failed[self.item.id])
        self.assertEqual(self.branch, git.current_branch(self.product))
        self.assertEqual('abandoning', self.repo.scan().valid[self.item.id].metadata['step'])

    def test_no_checkout_fails_without_finishing(self):
        self.runner.checkout = None
        self.at(self.item, 'abandoning')
        self.assertTrue(self.run_item(self.item))
        self.assertIn('needs a git repository', self.runner.failed[self.item.id])
        self.assertEqual('abandoning', self.repo.scan().valid[self.item.id].metadata['step'])

    def test_abandon_is_serialised_with_other_checkout_work(self):
        item = self.at(self.item, 'abandoning')
        self.runner.checkout_user = self.other.id
        self.assertFalse(self.run_item(item))
        self.assertIn(f'waiting for {self.other.id}', self.runner.waiting[self.item.id])
        self.assertEqual(self.branch, git.current_branch(self.product))

    def test_existing_done_accept_and_pull_request_items_remain_valid(self):
        for step in ('done', 'accept', 'pull-request'):
            with self.subTest(step=step):
                self.at(self.item, step)
                self.assertFalse(self.repo.scan().errors)
                self.assertEqual(step, self.repo.scan().valid[self.item.id].metadata['step'])


class AbandonThroughTheScreen(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        identity = patch.dict(os.environ, IDENTITY)
        identity.start()
        self.addCleanup(identity.stop)
        self.product = Path(self.temp.name) / 'product'
        subprocess.run(['git', 'init', '-q', '-b', 'main', str(self.product)], check=True)
        (self.product / 'app.txt').write_text('initial\n')
        git.commit_all(self.product, 'initial')
        self.repo = Repository(git.ensure_backlog(self.product))
        epic = self.repo.create('epic', 'Delivery')
        self.item = self.repo.create('story', 'Abandon me', parent=epic.id)
        self.runner = Runner(self.repo, engine=self.no_engine, report=lambda message: None,
                             checkout=self.product)
        self.branch = self.runner.take_checkout(self.item)
        (self.product / 'app.txt').write_text('recoverable work\n')
        git.commit_all(self.product, 'work to preserve')
        self.tip = git.must(self.product, 'rev-parse', 'HEAD')

    def no_engine(self, *args, **kwargs):
        self.fail('abandoning must not invoke an engine')

    def step(self):
        return self.repo.scan().valid[self.item.id].metadata['step']

    async def test_customer_abandons_at_either_step_without_a_note_and_the_branch_is_kept(self):
        from devteam import tui
        for step in ('accept', 'pull-request'):
            with self.subTest(step=step):
                current = self.repo.scan().valid[self.item.id]
                self.item.path.write_text(self.item.path.read_text().replace(
                    f"step: {current.metadata['step']}\n", f'step: {step}\n', 1))
                app = tui.Backlog(self.repo, self.runner)
                async with app.run_test(size=(120, 40)) as pilot:
                    await pilot.pause()
                    tree = app.query_one('#items')
                    nodes, queue = [], [tree.root]
                    while queue:
                        node = queue.pop(0)
                        nodes.append(node)
                        queue.extend(node.children)
                    tree.move_cursor(next(n for n in nodes if getattr(n.data, 'key', None) == self.item.id))
                    await pilot.pause()
                    await pilot.press('enter')
                    await pilot.pause()
                    self.assertIsInstance(app.screen, tui.Actions)
                    menu = app.screen.query_one('OptionList')
                    options = [str(o.prompt).split('  ')[0] for o in menu.options]
                    self.assertIn('abandon', options)
                    self.assertNotIn('accept', options)
                    menu.highlighted = options.index('abandon')
                    await pilot.press('enter')
                    await pilot.pause()
                    self.assertEqual(1, len(app.screen_stack))
                    self.assertEqual('abandoning', self.step())
                    self.assertNotIn('## Feedback', self.repo.scan().valid[self.item.id].body)
                current = self.repo.scan().valid[self.item.id]
                self.assertTrue(self.runner.run_item(current, self.repo.step(current)))
                self.assertEqual('abandoned', self.step())
                self.assertEqual('main', git.current_branch(self.product))
                self.assertEqual(self.tip, git.must(self.product, 'rev-parse', self.branch))
                git.must(self.product, 'checkout', '-q', self.branch)
