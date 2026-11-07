"""STORY-014: run evidence stays out of the committed record, and machine paths never reach git.

The harness is started as a process through its command line. The engines (claude, codex) and the
project's check (make) are stand-in executables on PATH; gh is the offline stub used elsewhere.
"""
from pathlib import Path
import re
import subprocess
import unittest
import unittest.mock


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


if __name__ == "__main__":
    unittest.main()
