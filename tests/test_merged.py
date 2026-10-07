"""Exercise merged's branching and failure recovery with real local git repositories."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from devteam import git
from devteam.backlog import Repository
from devteam.runner import Runner, StepFailed, Waiting, merged
from tests.test_checkout import IDENTITY


class Merged(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        identity = patch.dict(os.environ, IDENTITY)
        identity.start()
        self.addCleanup(identity.stop)
        root = Path(self.temp.name)
        self.remote = root / 'remote.git'
        self.product = root / 'product'
        self.writer = root / 'writer'
        subprocess.run(['git', 'init', '-q', '--bare', '-b', 'main', str(self.remote)], check=True)
        subprocess.run(['git', 'clone', '-q', str(self.remote), str(self.product)],
                       capture_output=True, check=True)
        (self.product / 'app.txt').write_text('initial\n')
        git.commit_all(self.product, 'initial')
        git.must(self.product, 'push', '-q', 'origin', 'main')
        subprocess.run(['git', 'clone', '-q', str(self.remote), str(self.writer)], check=True)
        self.repo = Repository(git.ensure_backlog(self.product))
        epic = self.repo.create('epic', 'Delivery')
        self.item = self.repo.create('story', 'Merged', parent=epic.id)
        self.other = self.repo.create('story', 'Next', parent=epic.id)
        self.item.path.write_text(self.item.path.read_text().replace('step: captured\n', 'step: merged\n'))
        self.messages = []
        self.runner = Runner(self.repo, engine=self.no_engine, report=self.messages.append,
                             checkout=self.product, max_runs=0)
        self.runner.take_checkout(self.item)
        stub_dir = root / 'bin'
        stub_dir.mkdir()
        self.gh_calls = root / 'gh-calls'
        stub = stub_dir / 'gh'
        stub.write_text(f'#!/bin/sh\necho called >> "{self.gh_calls}"\nexit 1\n')
        stub.chmod(0o755)
        path = patch.dict(os.environ, PATH=f"{stub_dir}{os.pathsep}{os.environ['PATH']}")
        path.start()
        self.addCleanup(path.stop)

    def no_engine(self, *args, **kwargs):
        self.fail('merged must not invoke an engine')

    def snapshot(self):
        return (git.must(self.product, 'rev-parse', 'HEAD'), git.current_branch(self.product),
                git.must(self.product, 'status', '--porcelain'),
                git.must(self.product, 'for-each-ref', '--format=%(refname) %(objectname)',
                         'refs/heads/main', 'refs/heads/devteam/'),
                git.must(self.product, 'diff', '--cached'),
                {p.name: p.read_bytes() for p in self.product.iterdir() if p.is_file()})

    def advance(self, directory, name):
        (directory / f'{name}.txt').write_text(name)
        git.commit_all(directory, name)
        return git.must(directory, 'rev-parse', 'HEAD')

    def done(self):
        self.assertEqual(1, self.runner.run_pass())
        item = self.repo.scan().valid[self.item.id]
        self.assertEqual('done', item.metadata['step'])
        self.assertTrue(self.repo.step(item).terminal)
        self.assertEqual('main', git.current_branch(self.product))
        self.assertTrue(git.has_ref(self.product, f'refs/heads/devteam/{self.item.id}'))
        self.assertIn('merged (harness: merged): completed -> done', self.messages[-1])
        self.assertEqual({}, self.runner.runs)
        self.assertFalse(self.gh_calls.exists())

    def failed(self, reason):
        before = self.snapshot()
        self.assertEqual(1, self.runner.run_pass())
        self.assertEqual(before, self.snapshot())
        self.assertEqual('merged', self.repo.scan().valid[self.item.id].metadata['step'])
        self.assertIn(reason, self.runner.failed[self.item.id])
        self.assertIn('merged (harness: merged): FAILED -', self.messages[-1])
        self.assertIn('; still at merged', self.messages[-1])
        self.assertEqual(0, self.runner.run_pass())

    def test_origin_ahead_from_item_base_or_unrelated_checkout(self):
        tip = self.advance(self.writer, 'remote')
        git.must(self.writer, 'push', '-q', 'origin', 'main')
        for branch in (f'devteam/{self.item.id}', 'main', 'other'):
            with self.subTest(branch=branch):
                git.must(self.product, 'branch', '-f', 'main', 'origin/main')
                if branch == 'other':
                    git.must(self.product, 'switch', '-q', '-c', branch)
                else:
                    git.must(self.product, 'switch', '-q', branch)
                self.item.path.write_text(self.item.path.read_text().replace('step: done\n', 'step: merged\n'))
                self.done()
                self.assertEqual(tip, git.must(self.product, 'rev-parse', 'main'))
                self.assertEqual('remote', (self.product / 'remote.txt').read_text())
                # Return to the item so main can be moved for the next subcase.
                git.must(self.product, 'switch', '-q', f'devteam/{self.item.id}')
                git.must(self.product, 'update-ref', 'refs/remotes/origin/main',
                         git.must(self.product, 'rev-parse', f'devteam/{self.item.id}'))

    def test_equal_and_local_ahead_keep_local_commits(self):
        for ahead in (False, True):
            with self.subTest(ahead=ahead):
                git.must(self.product, 'switch', '-q', 'main')
                if ahead:
                    self.advance(self.product, 'local')
                before = git.must(self.product, 'for-each-ref', '--format=%(refname) %(objectname)',
                                  'refs/heads/main', 'refs/heads/devteam/')
                self.item.path.write_text(self.item.path.read_text().replace('step: done\n', 'step: merged\n'))
                self.done()
                self.assertEqual(before, git.must(self.product, 'for-each-ref',
                                                 '--format=%(refname) %(objectname)',
                                                 'refs/heads/main', 'refs/heads/devteam/'))

    def test_dirty_tracked_and_untracked_fail_before_fetch(self):
        for name in ('app.txt', 'untracked.txt'):
            with self.subTest(name=name):
                path = self.product / name
                original = path.read_bytes() if path.exists() else None
                path.write_text('dirty')
                with self.assertRaisesRegex(StepFailed, f'uncommitted.*devteam/{self.item.id}'):
                    merged(self.runner, self.item)
                self.failed('uncommitted')
                with self.assertRaises(Waiting):
                    self.runner.take_checkout(self.other)
                if original is None:
                    path.unlink()
                else:
                    path.write_bytes(original)
                self.runner.retry(self.item.id)
        with self.assertRaises(Waiting):
            self.runner.take_checkout(self.other)
        self.done()
        self.assertEqual(f'devteam/{self.other.id}', self.runner.take_checkout(self.other))

    def test_diverged_fails_before_switch(self):
        git.must(self.product, 'switch', '-q', 'main')
        self.advance(self.product, 'local')
        git.must(self.product, 'switch', '-q', f'devteam/{self.item.id}')
        self.advance(self.writer, 'remote')
        git.must(self.writer, 'push', '-q', 'origin', 'main')
        self.failed('main has diverged')

    def test_fetch_failure_preserves_checkout(self):
        git.must(self.product, 'remote', 'set-url', 'origin', str(self.remote / 'missing'))
        self.failed('does not appear to be a git repository')

    def test_missing_base_and_refs_preserve_checkout(self):
        git.must(self.product, 'config', '--unset', f'branch.devteam/{self.item.id}.base')
        self.failed('no base branch is recorded')
        for base, expected in (('missing', 'refs/heads/missing'), ('local-only', 'refs/remotes/origin/local-only')):
            with self.subTest(base=base):
                git.must(self.product, 'config', f'branch.devteam/{self.item.id}.base', base)
                if base == 'local-only':
                    git.must(self.product, 'branch', base)
                self.runner.retry(self.item.id)
                self.failed(expected)
