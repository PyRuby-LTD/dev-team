"""Sync and publication safety using real repositories and runner transitions."""
import unittest

from devteam import git, workflow
from devteam.runner import StepFailed, sync
from tests import test_merged


class Sync(unittest.TestCase):
    advance = test_merged.Merged.advance

    def setUp(self):
        test_merged.Merged.setUp(self)
        self.branch = f'devteam/{self.item.id}'
        self.runner.max_runs = 20
        self.at('sync')

    def no_engine(self, *args, **kwargs):
        self.fail('sync must not invoke an engine')

    def at(self, step):
        current = self.repo.scan().valid[self.item.id]
        self.item.path.write_text(self.item.path.read_text().replace(
            f'step: {current.metadata["step"]}\n', f'step: {step}\n'))

    def head(self, ref='HEAD', directory=None):
        return git.must(directory or self.product, 'rev-parse', ref)

    def base_change(self, text=None):
        if text is None:
            self.advance(self.writer, 'base')
        else:
            (self.writer / 'app.txt').write_text(text)
            git.commit_all(self.writer, 'base change')
        git.must(self.writer, 'push', '-q', 'origin', 'main')
        return self.head(directory=self.writer)

    def conflict(self):
        (self.product / 'app.txt').write_text('story\n')
        git.commit_all(self.product, 'story change')
        self.previous = self.head()
        self.base = self.base_change('base\n')
        self.runner.run_pass()
        self.assertEqual('resolve', self.repo.scan().valid[self.item.id].metadata['step'])
        self.assertTrue(git.merging(self.product))
        self.assertEqual(self.previous, self.head())
        self.assertIn('<<<<<<<', (self.product / 'app.txt').read_text())
        self.assertFalse((self.product / '.git' / 'rebase-merge').exists())
        self.assertFalse((self.product / '.git' / 'rebase-apply').exists())

    def resolve(self, reply='resolved', text='resolved\n'):
        def engine(role, prompt, cwd, extra, log):
            self.assertIn('- app.txt', prompt)
            self.assertIn('origin/main', prompt)
            if text is not None:
                (cwd / 'app.txt').write_text(text)
            return 0, f'TRANSITION: {reply}'
        self.runner.engine = engine
        self.runner.run_pass()

    def test_sync_claims_checkout_and_waits_for_other_users(self):
        record = self.repo.scan().valid[self.item.id]
        step = self.repo.step(record)
        self.runner.checkout_user = self.other.id
        self.assertFalse(self.runner.claim(record, step))
        self.runner.checkout_user = None
        self.assertTrue(self.runner.claim(record, step))
        self.assertEqual(self.item.id, self.runner.checkout_user)
        self.assertEqual(set(), self.runner.active - {self.item.id})

    def test_publish_conflict_and_verification_failure_route(self):
        self.at('sync-publish')
        (self.product / 'app.txt').write_text('story\n')
        git.commit_all(self.product, 'story')
        self.base_change('base\n')
        self.runner.run_pass()
        self.assertEqual('resolve-publish', self.repo.scan().valid[self.item.id].metadata['step'])
        self.resolve()
        self.assertEqual('verify-publish', self.repo.scan().valid[self.item.id].metadata['step'])
        self.runner.check = lambda *args, **kwargs: (1, 'failed')
        self.runner.run_pass()
        self.assertEqual('implement', self.repo.scan().valid[self.item.id].metadata['step'])
        self.at('verify')
        self.runner.run_pass()
        self.assertEqual('test', self.repo.scan().valid[self.item.id].metadata['step'])

    def test_clean_rebase_and_noop(self):
        self.advance(self.product, 'story')
        base = self.base_change()
        self.runner.run_pass()
        self.assertEqual('verify', self.repo.scan().valid[self.item.id].metadata['step'])
        self.assertEqual(0, git.run(self.product, 'merge-base', '--is-ancestor', base, 'HEAD').returncode)
        self.assertEqual('story', (self.product / 'story.txt').read_text())
        head = self.head()
        self.assertEqual('completed', sync(self.runner, self.item))
        self.assertEqual(head, self.head())

    def test_conflict_resolution_and_later_merge_preserve_parents(self):
        self.conflict()
        self.resolve()
        merge = self.head()
        self.assertEqual([merge, self.previous, self.base],
                         git.must(self.product, 'rev-list', '--parents', '-n', '1', 'HEAD').split())
        self.assertTrue(git.clean(self.product))
        self.base_change()
        self.assertEqual('completed', sync(self.runner, self.item))
        self.assertEqual(merge, self.head('HEAD^1'))
        self.assertTrue(git.clean(self.product))

    def test_markers_fail_and_retry_even_when_staged(self):
        self.conflict()
        git.must(self.product, 'add', 'app.txt')
        self.resolve(text=None)
        self.assertIn('conflict markers', self.runner.failed[self.item.id])
        self.assertEqual(self.previous, self.head())
        self.assertTrue(git.merging(self.product))
        self.runner.retry(self.item.id)
        self.resolve()
        self.assertTrue(git.clean(self.product))

    def test_blocked_aborts(self):
        self.conflict()
        (self.product / 'resolution-notes.txt').write_text('unfinished resolution')
        self.resolve('blocked')
        self.assertEqual(self.previous, self.head())
        self.assertTrue(git.clean(self.product))
        self.assertFalse(git.merging(self.product))
        self.assertEqual('ready', self.repo.scan().valid[self.item.id].metadata['step'])

    def test_rebase_conflicts_but_final_tree_merges_cleanly(self):
        (self.product / 'app.txt').write_text('temporary\n')
        git.commit_all(self.product, 'temporary')
        (self.product / 'app.txt').write_text('initial\n')
        git.commit_all(self.product, 'restore')
        before = self.head()
        base = self.base_change('base\n')
        self.assertEqual('completed', sync(self.runner, self.item))
        self.assertEqual([self.head(), before, base],
                         git.must(self.product, 'rev-list', '--parents', '-n', '1', 'HEAD').split())
        self.assertTrue(git.clean(self.product))

    def test_preconditions_preserve_checkout(self):
        before = self.head()
        for failure in ('dirty', 'unrecorded', 'missing', 'unfetchable'):
            with self.subTest(failure=failure):
                git.must(self.product, 'config', f'branch.{self.branch}.base', 'main')
                if failure == 'dirty':
                    (self.product / 'dirty').write_text('dirty')
                elif failure == 'unrecorded':
                    git.must(self.product, 'config', '--unset', f'branch.{self.branch}.base')
                elif failure == 'missing':
                    git.must(self.product, 'config', f'branch.{self.branch}.base', 'missing')
                else:
                    git.must(self.product, 'remote', 'set-url', 'origin', str(self.remote / 'missing'))
                with self.assertRaises((StepFailed, git.GitError)):
                    sync(self.runner, self.item)
                self.assertEqual(before, self.head())
                self.assertEqual(self.branch, git.current_branch(self.product))
                (self.product / 'dirty').unlink(missing_ok=True)

    def test_republish_with_and_without_record(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                self.advance(self.product, f'A{legacy}')
                self.advance(self.product, f'B{legacy}')
                git.push_branch(self.product, self.branch)
                if legacy:
                    git.must(self.product, 'config', '--unset', f'branch.{self.branch}.pushed')
                self.advance(self.product, f'C{legacy}')
                self.base_change()
                self.assertEqual('completed', sync(self.runner, self.item))
                self.assertEqual('completed', sync(self.runner, self.item))
                git.push_branch(self.product, self.branch)
                self.assertEqual(self.head(), self.head(f'refs/heads/{self.branch}', self.remote))

    def foreign(self):
        self.advance(self.product, 'A')
        git.push_branch(self.product, self.branch)
        old = self.head()
        git.fetch(self.writer, 'origin')
        git.must(self.writer, 'switch', '-q', '-c', self.branch, f'origin/{self.branch}')
        foreign = self.advance(self.writer, 'suggestion')
        git.must(self.writer, 'push', '-q', 'origin', self.branch)
        return old, foreign

    def test_foreign_commits_fail_sync_and_push_then_pull_recovery(self):
        old, foreign = self.foreign()
        for action in (lambda: sync(self.runner, self.item), lambda: git.push_branch(self.product, self.branch)):
            with self.assertRaisesRegex(git.GitError, foreign[:7]):
                action()
            self.assertEqual(old, self.head())
            self.assertEqual(old, git.pushed_head(self.product, self.branch))
            self.assertEqual(foreign, self.head(f'refs/heads/{self.branch}', self.remote))
        git.must(self.product, 'merge', f'origin/{self.branch}')
        git.must(self.writer, 'switch', '-q', 'main')
        self.base_change()
        sync(self.runner, self.item)
        sync(self.runner, self.item)
        git.push_branch(self.product, self.branch)
        self.assertEqual('suggestion', (self.product / 'suggestion.txt').read_text())
        self.assertEqual(self.head(), self.head(f'refs/heads/{self.branch}', self.remote))

    def test_discard_recovery(self):
        old, foreign = self.foreign()
        with self.assertRaisesRegex(git.GitError, foreign[:7]):
            sync(self.runner, self.item)
        git.must(self.writer, 'push', '--force', 'origin', f'{old}:refs/heads/{self.branch}')
        git.must(self.writer, 'switch', '-q', 'main')
        self.base_change()
        sync(self.runner, self.item)
        git.push_branch(self.product, self.branch)
        self.assertFalse((self.product / 'suggestion.txt').exists())
        self.assertEqual(self.head(), self.head(f'refs/heads/{self.branch}', self.remote))


class SyncWorkflow(unittest.TestCase):
    def test_harness_validation(self):
        for action, outcomes, valid in (
            ('sync', ['completed', 'conflicted'], True), ('sync', ['completed'], False),
            ('merged', ['completed', 'conflicted'], False), ('unknown', ['completed'], False)):
            data = {'initial': 'a', 'steps': {'a': {'owner': f'harness:{action}',
                    'transitions': {name: 'a' for name in outcomes}}}}
            if valid:
                workflow.build('test', data, [])
            else:
                with self.assertRaises(workflow.InvalidWorkflow):
                    workflow.build('test', data, [])
