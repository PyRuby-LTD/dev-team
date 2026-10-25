"""STORY-023: a long-running `dev-team run` notices a merged pull request and finishes the item by itself."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
STUBS = ROOT / "tests" / "stubs"
TO_PULL_REQUEST = ("analyse", "analysed", "sound", "play", "implemented", "written", "passed", "approve",
                   "pr", "published")
IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


class MergedPullRequestDetectedFromTheCommandLine(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.remote = self.directory / "remote.git"
        self.product = self.directory / "product"
        self.bin = self.directory / "bin"
        self.bin.mkdir()
        shutil.copy(STUBS / "gh", self.bin / "gh")
        (self.bin / "gh").chmod(0o755)
        self.gh_argv = self.directory / "gh-argv.jsonl"

        self.git("init", "-q", "--bare", "-b", "main", str(self.remote))
        self.git("clone", "-q", str(self.remote), str(self.product))
        (self.product / "app.txt").write_text("initial\n")
        self.git("add", "-A", cwd=self.product)
        self.git("commit", "-q", "-m", "initial", cwd=self.product)
        self.git("push", "-q", "origin", "main", cwd=self.product)

        body = self.directory / "body.md"
        body.write_text("## Pull request\n\nhttps://github.com/acme/product/pull/1\n")
        self.devteam("backlog", "capture", "epic", "Epic", "--id", "EPIC-001")
        self.devteam("backlog", "capture", "story", "Story", "--id", "STORY-001", "--parent", "EPIC-001",
                     "--file", str(body))
        for transition in TO_PULL_REQUEST:
            self.devteam("backlog", "move", "STORY-001", transition)
        self.git("switch", "-q", "-c", "devteam/STORY-001", cwd=self.product)
        self.git("config", "branch.devteam/STORY-001.base", "main", cwd=self.product)

    def git(self, *args, cwd=None):
        return subprocess.run(["git", *args], cwd=cwd or self.directory, env={**os.environ, **IDENTITY},
                              capture_output=True, text=True, check=True).stdout.strip()

    def env(self, state):
        fixtures = self.directory / "fixtures"
        fixtures.mkdir(exist_ok=True)
        (fixtures / "state.json").write_text(json.dumps({"state": state, "reviewDecision": ""}))
        return {**os.environ, **IDENTITY, "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
                "GH_STUB_ARGV": str(self.gh_argv), "GH_STUB_FIXTURES": str(fixtures),
                "GH_STUB_FAIL": "", "GH_STUB_SLEEP": ""}

    def devteam(self, *args):
        return subprocess.run([sys.executable, "-m", "devteam", "--product", str(self.product), *args],
                              cwd=ROOT, env={**os.environ, **IDENTITY},
                              capture_output=True, text=True, timeout=60, check=True)

    def step(self):
        listing = self.devteam("backlog", "list").stdout
        return next(line.split()[1] for line in listing.splitlines() if line.startswith("STORY-001"))

    def run_until(self, state, expected, seconds):
        process = subprocess.Popen([sys.executable, "-m", "devteam", "--product", str(self.product), "run"],
                                   cwd=ROOT, env=self.env(state), stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True)
        deadline = time.monotonic() + seconds
        try:
            while time.monotonic() < deadline and self.step() != expected:
                time.sleep(0.2)
            reached = self.step()
        finally:
            process.terminate()
            output = process.communicate(timeout=30)[0]
        return reached, output

    def lookups(self):
        if not self.gh_argv.exists():
            return []
        return [call for call in map(json.loads, self.gh_argv.read_text().splitlines()) if call[:2] == ["pr", "view"]]

    def test_item_reaches_done_once_its_pull_request_is_merged_on_github(self):
        reached, output = self.run_until("MERGED", "done", seconds=30)
        self.assertEqual("done", reached, output)
        self.assertEqual("main", self.git("branch", "--show-current", cwd=self.product))
        self.assertTrue(self.lookups())

    def test_item_stays_at_pull_request_while_the_pull_request_is_not_merged(self):
        reached, output = self.run_until("OPEN", "done", seconds=4)
        self.assertEqual("pull-request", reached, output)
        self.assertTrue(self.lookups(), "the runner should have looked the pull request up")


if __name__ == "__main__":
    unittest.main()
