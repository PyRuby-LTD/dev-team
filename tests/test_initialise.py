import contextlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from devteam import config, git
from devteam.initialise import github_origin, has_regression, initialise, quick_start
from tests.test_checkout import IDENTITY


class Parsing(unittest.TestCase):
    def test_github_origin_requires_exact_host_and_supported_form(self):
        for url in ('https://github.com/o/r', 'https://github.com/o/r.git',
                    'git@github.com:o/r.git', 'ssh://git@github.com/o/r'):
            with self.subTest(url=url):
                self.assertTrue(github_origin(url))
        for url in ('', 'https://github.com.example.com/o/r', 'git@alias:o/r',
                    'https://github.com/o/r/extra', 'https://github.com/o',
                    'https://github.com/o/r?query', 'ssh://github.com/o/r'):
            with self.subTest(url=url):
                self.assertFalse(github_origin(url))

    def test_regression_target_and_false_positives(self):
        for text in ('regression:\n\ttrue', 'all regression: dep', 'regression:: dep'):
            self.assertTrue(has_regression(text))
        for text in ('# regression: later', '\techo regression:', '.PHONY: regression',
                     'regression := test', 'TARGETS = regression: dep', 'all: regression'):
            self.assertFalse(has_regression(text))

    def test_command_path_validation(self):
        with patch.object(config, 'ROOT', Path('/tmp/team')):
            self.assertEqual('uv run --project /tmp/team python -P -m devteam', config.harness_command())
        for char in ' \t\n*?[]()"\'\\':
            with self.subTest(char=char), patch.object(config, 'ROOT', Path('/tmp/team' + char)):
                with self.assertRaisesRegex(ValueError, 'Harness checkout path'):
                    config.harness_command()


class SetupState(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.product = self.root / 'product'
        self.remote = self.root / 'remote.git'
        env = patch.dict(os.environ, IDENTITY)
        env.start()
        self.addCleanup(env.stop)
        subprocess.run(['git', 'init', '-q', '-b', 'main', str(self.product)], check=True)
        subprocess.run(['git', 'init', '-q', '--bare', str(self.remote)], check=True)
        git.must(self.product, 'remote', 'add', 'origin', 'git@github.com:o/r.git')
        git.must(self.product, 'config', f'url.{self.remote}.insteadOf', 'git@github.com:o/r.git')

    def initialise(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            initialise(self.product)
        return output.getvalue()

    def test_unborn_branch_ignores_backlog_history_and_preserves_other_staged_files(self):
        git.ensure_backlog(self.product)
        self.assertTrue(quick_start(self.product))
        (self.product / 'other').write_text('leave me')
        git.must(self.product, 'add', 'other')
        (self.product / 'Makefile').write_text('regression:\n\tfalse\n')
        self.initialise()
        self.assertEqual('Makefile', git.must(self.product, 'ls-tree', '--name-only', 'HEAD'))
        self.assertEqual('A  other', git.must(self.product, 'status', '--porcelain'))
        self.assertTrue(quick_start(self.product))
        self.assertEqual(git.must(self.product, 'rev-parse', 'HEAD'),
                         git.must(self.remote, 'rev-parse', 'refs/heads/main'))
        before = git.must(self.product, 'rev-parse', 'HEAD')
        self.assertIn('already set up', self.initialise())
        self.assertEqual(before, git.must(self.product, 'rev-parse', 'HEAD'))

    def test_existing_codebase_does_not_commit_or_push(self):
        for value in ('one', 'two'):
            (self.product / 'app').write_text(value)
            git.commit_all(self.product, value)
        before = git.must(self.product, 'rev-parse', 'HEAD')
        self.assertFalse(quick_start(self.product))
        self.assertIn('Wire up make regression and commit', self.initialise())
        self.assertEqual(before, git.must(self.product, 'rev-parse', 'HEAD'))
        self.assertEqual('', git.run(self.remote, 'show-ref').stdout)
        self.assertEqual('?? Makefile', git.must(self.product, 'status', '--porcelain'))

    def test_one_root_commit_with_other_files_is_existing_codebase(self):
        (self.product / 'app').write_text('app')
        (self.product / 'Makefile').write_text('regression:\n\ttrue\n')
        git.commit_all(self.product, 'code')
        self.assertFalse(quick_start(self.product))
        head = git.must(self.product, 'rev-parse', 'HEAD')
        self.initialise()
        self.assertEqual(head, git.must(self.product, 'rev-parse', 'HEAD'))
        self.assertEqual('', git.run(self.remote, 'show-ref').stdout)

    def test_push_failure_can_be_retried_without_another_commit(self):
        missing = self.root / 'missing.git'
        git.must(self.product, 'config', '--unset-all', f'url.{self.remote}.insteadOf')
        git.must(self.product, 'config', f'url.{missing}.insteadOf', 'git@github.com:o/r.git')
        with self.assertRaises(git.GitError):
            self.initialise()
        head = git.must(self.product, 'rev-parse', 'HEAD')
        self.assertFalse((self.product / 'backlog').exists())
        subprocess.run(['git', 'init', '-q', '--bare', str(missing)], check=True)
        self.initialise()
        self.assertEqual(head, git.must(missing, 'rev-parse', 'refs/heads/main'))
        self.assertEqual('1', git.must(self.product, 'rev-list', '--count', 'HEAD'))

    def test_different_origin_commit_is_not_overwritten(self):
        other = self.root / 'other'
        subprocess.run(['git', 'clone', '-q', str(self.remote), str(other)], check=True,
                       capture_output=True)
        git.must(other, 'switch', '-c', 'main')
        (other / 'app').write_text('remote')
        git.commit_all(other, 'remote')
        git.must(other, 'push', 'origin', 'main')
        remote_head = git.must(self.remote, 'rev-parse', 'refs/heads/main')
        self.assertIn('different commit; nothing pushed', self.initialise())
        self.assertEqual(remote_head, git.must(self.remote, 'rev-parse', 'refs/heads/main'))

    def test_missing_identity_failure_leaves_makefile_for_retry(self):
        git.must(self.product, 'config', 'user.useConfigOnly', 'true')
        env = {key: value for key, value in os.environ.items() if key not in IDENTITY}
        env.update(GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_SYSTEM='/dev/null')
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(git.GitError, 'identity|name|email'):
                self.initialise()
        self.assertTrue((self.product / 'Makefile').exists())
        self.assertFalse(git.has_ref(self.product, 'HEAD'))
        self.assertFalse((self.product / 'backlog').exists())
        self.initialise()
        self.assertEqual('1', git.must(self.product, 'rev-list', '--count', 'HEAD'))
