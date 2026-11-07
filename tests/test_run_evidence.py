"""STORY-014: run evidence stays out of the committed record, and machine paths never reach git.

The harness is started as a process through its command line. The engines (claude, codex) and the
project's check (make) are stand-in executables on PATH; gh is the offline stub used elsewhere.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
import unittest.mock

from textual.widgets import TextArea, Tree

from devteam import git as repo_git
from devteam import tui
from devteam.backlog import Repository
from devteam.config import Role
from devteam.evidence import PathGuard
from devteam.runner import Runner

ROOT = Path(__file__).resolve().parents[1]
STUBS = ROOT / "tests" / "stubs"
FIXTURES = ROOT / "tests" / "fixtures" / "gh"
IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
ISOLATED_GIT = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
TO_VERIFY = ("analyse", "analysed", "sound", "play", "implemented", "written", "completed")
TO_ACCEPT = TO_VERIFY + ("passed", "approve")
TO_PULL_REQUEST = TO_ACCEPT + ("pr", "completed", "passed", "published")
# Built at run time so that this file does not hold a home-style path itself.
NAME = "fixture" + "person"
HOME = "/home/" + NAME
STAMP = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC")

MAKE = """#!/bin/sh
echo "$@" > "$STUB_MAKE_ARGS"
printf '%s\\n' "$CHECK_OUTPUT"
exit "${CHECK_EXIT:-0}"
"""


def section(text, name):
    found = re.search(rf"^## {name}\n(.*?)(?=^## |\Z)", text, re.DOTALL | re.MULTILINE)
    return found.group(1) if found else None


def flat(text):
    return " ".join(text.split())


class TestRecordsAlreadyCompleted(unittest.TestCase):
    def test_records_that_existed_before_this_story_are_unchanged(self):
        def git(*args):
            return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
        if git("rev-parse", "--verify", "-q", "main").returncode:
            self.skipTest("no main branch to compare with")
        changes = git("diff", "--name-status", "main", "--", "docs/work-items").stdout.splitlines()
        self.assertEqual([], [line for line in changes if not line.startswith("A")])


class TestTerminalNotification(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.product = base / "product"
        env = {**IDENTITY, **ISOLATED_GIT}
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.product)], check=True, env={**os.environ, **env})
        (self.product / "app.txt").write_text("v1\n")
        with unittest.mock.patch.dict(os.environ, env):
            repo_git.commit_all(self.product, "init")
            backlog = repo_git.ensure_backlog(self.product)
            workflows = base / "workflows"
            workflows.mkdir()
            (workflows / "default.json").write_text(json.dumps({
                "initial": "captured",
                "steps": {"captured": {"owner": "human", "transitions": {"analyse": "analysis"}},
                          "analysis": {"owner": "agent:analyst", "transitions": {"ready": "done"}},
                          "done": {"owner": "human", "transitions": {}}}}))
            self.repo = Repository(backlog, workflows, {"analyst"}, guard=PathGuard(self.product))
            self.story = self.repo.create("story", "Story", parent=self.repo.create("epic", "Epic").id)
            self.repo.transition(self.story.id, "analyse")
        self.backlog = backlog
        role = Role("analyst", "fake", "m", 5, ["fake"], "w")
        self.runner = Runner(Repository(backlog, workflows, {"analyst": role}, guard=PathGuard(self.product)),
                             {"analyst": role}, lambda *args, **kwargs: (97, ""), lambda message: None)

    async def test_a_typed_note_with_a_home_path_is_masked_and_the_customer_is_told(self):
        env = {**IDENTITY, **ISOLATED_GIT}
        with unittest.mock.patch.dict(os.environ, env):
            app = tui.Backlog(self.repo, self.runner)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                tree = app.query_one(Tree)
                pending = list(tree.root.children)
                nodes = []
                while pending:
                    node = pending.pop()
                    nodes.append(node)
                    pending.extend(node.children)
                tree.move_cursor(next(n for n in nodes if n.data.key == self.story.id))
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                self.assertIsInstance(app.screen, tui.Note)
                app.screen.query_one(TextArea).text = f"Look in {HOME}/work for it"
                await pilot.press("ctrl+s")
                await pilot.pause()
                messages = [notification.message for notification in app._notifications]
        self.assertTrue(any("masked lines" in message and "backlog/log/STORY-001/unmasked-" in message
                            for message in messages), messages)
        self.assertFalse(any(NAME in message for message in messages))
        history = subprocess.run(["git", "log", "-p", "devteam-backlog"], cwd=self.backlog, capture_output=True,
                                 text=True).stdout
        self.assertNotIn(NAME, history)
        self.assertIn("Look in <path> for it", (self.backlog / "stories" / "STORY-001.md").read_text())


if __name__ == "__main__":
    unittest.main()
