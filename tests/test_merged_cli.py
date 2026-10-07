"""STORY-011: marking a pull request merged brings local main in line with origin, driven through the devteam command line."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
STUBS = ROOT / "tests" / "stubs"
STREAMS = ROOT / "tests" / "fixtures" / "streams"
TO_PULL_REQUEST = ("analyse", "analysed", "sound", "play", "implemented", "written", "passed", "approve",
                   "pr", "published")
IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


class MergedFromTheCommandLine(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.remote = self.directory / "remote.git"
        self.product = self.directory / "product"
        self.writer = self.directory / "writer"
        self.bin = self.directory / "bin"
        self.bin.mkdir()
        shutil.copy(STUBS / "claude", self.bin / "claude")
        (self.bin / "claude").chmod(0o755)
        gh = self.bin / "gh"
        self.gh_calls = self.directory / "gh-calls"
        gh.write_text(f'#!/bin/sh\necho called >> "{self.gh_calls}"\nexit 1\n')
        gh.chmod(0o755)
        self.argv = self.directory / "argv.json"

        self.git("init", "-q", "--bare", "-b", "main", str(self.remote), cwd=self.directory)
        self.git("clone", "-q", str(self.remote), str(self.product), cwd=self.directory)
        (self.product / "app.txt").write_text("initial\n")
        self.commit(self.product, "initial")
        self.git("push", "-q", "origin", "main", cwd=self.product)
        self.git("clone", "-q", str(self.remote), str(self.writer), cwd=self.directory)

        self.devteam("backlog", "capture", "epic", "Epic", "--id", "EPIC-001")
        self.devteam("backlog", "capture", "story", "Story", "--id", "STORY-001", "--parent", "EPIC-001")
        for transition in TO_PULL_REQUEST:
            self.devteam("backlog", "move", "STORY-001", transition)
        self.git("switch", "-q", "-c", "devteam/STORY-001", cwd=self.product)
        self.git("config", "branch.devteam/STORY-001.base", "main", cwd=self.product)
        self.devteam("backlog", "move", "STORY-001", "merged")

    def git(self, *args, cwd):
        return subprocess.run(["git", *args], cwd=cwd, env={**os.environ, **IDENTITY},
                              capture_output=True, text=True, check=True).stdout.strip()

    def commit(self, directory, name):
        (directory / f"{name}.txt").write_text(name)
        self.git("add", "-A", cwd=directory)
        self.git("commit", "-q", "-m", name, cwd=directory)
        return self.git("rev-parse", "HEAD", cwd=directory)

    def devteam(self, *args, env=None):
        return subprocess.run([sys.executable, "-m", "devteam", "--product", str(self.product), *args],
                              cwd=ROOT, env={**os.environ, **IDENTITY, **(env or {})},
                              capture_output=True, text=True, timeout=60, check=True)

    def run_once(self):
        env = {"PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}", "STUB_ARGV": str(self.argv),
               "STUB_STDOUT": str(STREAMS / "success.jsonl")}
        return self.devteam("run", "--once", env=env)

    def step(self):
        listing = self.devteam("backlog", "list").stdout
        return next(line.split()[1] for line in listing.splitlines() if line.startswith("STORY-001"))

    def snapshot(self):
        return (self.git("rev-parse", "HEAD", cwd=self.product),
                self.git("branch", "--show-current", cwd=self.product),
                self.git("status", "--porcelain", cwd=self.product),
                self.git("for-each-ref", "--format=%(refname) %(objectname)", "refs/heads/main",
                         "refs/heads/devteam/", cwd=self.product),
                (self.product / "app.txt").read_text())

    def push_from_writer(self, name):
        tip = self.commit(self.writer, name)
        self.git("push", "-q", "origin", "main", cwd=self.writer)
        return tip

    def assert_not_invoked(self):
        self.assertFalse(self.argv.exists(), "no agent should run for a harness step")
        self.assertFalse(self.gh_calls.exists(), "gh must not be called")

    def test_merged_fast_forwards_local_main_to_origin_and_finishes_the_item(self):
        tip = self.push_from_writer("upstream")
        result = self.run_once()
        self.assertIn("merged (harness: merged): completed -> done", result.stdout)
        self.assertEqual("done", self.step())
        self.assertEqual("main", self.git("branch", "--show-current", cwd=self.product))
        self.assertEqual(tip, self.git("rev-parse", "main", cwd=self.product))
        self.assertEqual(tip, self.git("rev-parse", "origin/main", cwd=self.product))
        self.git("rev-parse", "--verify", "refs/heads/devteam/STORY-001", cwd=self.product)
        self.assertEqual("upstream", (self.product / "upstream.txt").read_text())
        self.assert_not_invoked()

    def test_merged_succeeds_when_main_already_matches_origin(self):
        before = self.git("rev-parse", "main", cwd=self.product)
        self.run_once()
        self.assertEqual("done", self.step())
        self.assertEqual(before, self.git("rev-parse", "main", cwd=self.product))

    def test_merged_keeps_unpushed_local_commits_on_main(self):
        self.git("switch", "-q", "main", cwd=self.product)
        local = self.commit(self.product, "local")
        self.git("switch", "-q", "devteam/STORY-001", cwd=self.product)
        self.run_once()
        self.assertEqual("done", self.step())
        self.assertEqual(local, self.git("rev-parse", "main", cwd=self.product))
        self.assertEqual("main", self.git("branch", "--show-current", cwd=self.product))

    def test_dirty_checkout_fails_the_step_and_leaves_the_repository_untouched(self):
        self.push_from_writer("upstream")
        for name in ("app.txt", "scratch.txt"):
            with self.subTest(name=name):
                (self.product / name).write_text("dirty")
                before = self.snapshot()
                result = self.run_once()
                output = result.stdout + result.stderr
                self.assertRegex(output, r"merged .*FAILED - .*uncommitted.*devteam/STORY-001.*still at merged")
                self.assertEqual("merged", self.step())
                self.assertEqual(before, self.snapshot())
                self.assert_not_invoked()
                (self.product / name).unlink() if name == "scratch.txt" else self.git(
                    "checkout", "--", name, cwd=self.product)

    def test_diverged_main_fails_the_step_and_leaves_the_repository_untouched(self):
        self.git("switch", "-q", "main", cwd=self.product)
        self.commit(self.product, "local")
        self.git("switch", "-q", "devteam/STORY-001", cwd=self.product)
        self.push_from_writer("upstream")
        before = self.snapshot()
        result = self.run_once()
        output = result.stdout + result.stderr
        self.assertRegex(output, r"merged .*FAILED - .*diverged.*main.*still at merged")
        self.assertEqual("merged", self.step())
        self.assertEqual(before, self.snapshot())
        self.assert_not_invoked()

    def test_unreachable_origin_fails_the_step_and_leaves_the_repository_untouched(self):
        self.git("remote", "set-url", "origin", str(self.directory / "nowhere.git"), cwd=self.product)
        before = self.snapshot()
        result = self.run_once()
        self.assertRegex(result.stdout + result.stderr,
                         r"(?s)merged .*FAILED - git fetch origin:.*does not appear to be a git repository.*still at merged")
        self.assertEqual("merged", self.step())
        self.assertEqual(before, self.snapshot())

    def test_failed_step_is_retried_after_the_cause_is_fixed_by_restarting(self):
        (self.product / "scratch.txt").write_text("dirty")
        self.run_once()
        self.assertEqual("merged", self.step())
        (self.product / "scratch.txt").unlink()
        self.run_once()
        self.assertEqual("done", self.step())


class MergedSourceAndDocumentation(unittest.TestCase):
    def test_exactly_one_merged_action_is_registered_and_no_pr_is_merged_by_the_tool(self):
        runner = (ROOT / "devteam" / "runner.py").read_text()
        self.assertEqual(1, len(re.findall(r'"merged"\s*:', runner)))
        for source in (ROOT / "devteam").glob("*.py"):
            self.assertNotIn("gh pr merge", source.read_text(), source.name)
            self.assertNotRegex(source.read_text(), r'"pr",\s*"merge"', source.name)

    def test_readme_describes_merged_failures_and_recovery(self):
        readme = (ROOT / "README.md").read_text()
        for phrase in ("fast-forwards", "dirty checkout", "diverged", "`t`", "retry"):
            self.assertIn(phrase, readme)


if __name__ == "__main__":
    unittest.main()
