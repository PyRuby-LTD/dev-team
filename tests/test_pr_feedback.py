"""Parsing and rendering of rejected PR feedback, using only an offline gh."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from devteam import questions, runner
from devteam.backlog import Repository

ROOT = Path(__file__).resolve().parents[1]


class PullRequestFeedback(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        shutil.copy(ROOT / "tests/stubs/gh", self.bin / "gh")
        (self.bin / "gh").chmod(0o755)
        (self.bin / "python3").symlink_to(sys.executable)
        self.fixtures = self.root / "fixtures"
        # Baseline fixtures are modelled on real gh output, not captured from it.
        shutil.copytree(ROOT / "tests/fixtures/gh", self.fixtures)
        self.argv = self.root / "argv.jsonl"
        env = {"PATH": str(self.bin), "GH_STUB_ARGV": str(self.argv),
               "GH_STUB_FIXTURES": str(self.fixtures), "GH_STUB_FAIL": "", "GH_STUB_SLEEP": ""}
        self.environment = patch.dict(os.environ, env)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.repo = Repository(self.root / "backlog")
        epic = self.repo.create("epic", "Epic")
        self.story = self.repo.create("story", "Story", parent=epic.id)
        self.body = ("## Pull request\n\nhttps://github.com/acme/product/pull/1\n"
                     "https://github.com/acme/product/pull/2\n\n"
                     "## Pull request feedback\n\nOld feedback\n\n"
                     "## Feedback\n\nCustomer note\n\n## Implementation\n\nKeep this\n")
        self.reset()
        self.messages = []
        self.runner = runner.Runner(self.repo, report=self.messages.append)

    def reset(self, body=None):
        self.repo.write_body(self.story.id, self.body if body is None else body, "fixture")
        record = self.record()
        record.path.write_text(record.path.read_text().replace(
            f"step: {record.metadata['step']}\n", "step: rejected\n", 1))

    def record(self):
        return self.repo.scan().valid[self.story.id]

    def fixture(self, kind, data):
        (self.fixtures / f"{kind}.json").write_text(data)

    def test_baseline_and_last_url(self):
        self.runner.run_pass()
        text = self.record().body
        self.assertEqual("implement", self.record().metadata["step"])
        self.assertEqual(1, text.count("Review (COMMENTED)"))
        self.assertIn("**Inline comment** by bob on workflows/default.json line 16", text)
        self.assertIn("Please address the review before merging.", text)
        self.assertIn("2026-03-01T10:00:00Z", text)
        self.assertNotIn("Old feedback", text)
        self.assertTrue(text.endswith("## Feedback\n\nCustomer note\n\n## Implementation\n\nKeep this\n"))
        calls = [json.loads(line) for line in self.argv.read_text().splitlines()]
        self.assertEqual([["api", f"repos/acme/product/{suffix}", "--paginate"] for suffix in
                          ("pulls/2/reviews", "pulls/2/comments", "issues/2/comments")], calls)

    def test_pagination_pending_and_inline_locations(self):
        reviews = json.loads((self.fixtures / "reviews.json").read_text())
        self.assertEqual(["COMMENTED", "COMMENTED"], [r["state"] for r in reviews])
        reviews += [{"state": "PENDING", "body": "Unsubmitted", "submitted_at": None},
                    {"state": "COMMENTED", "body": "No submission date"}]
        self.fixture("reviews", json.dumps(reviews))
        self.fixture("inline", json.dumps([{"user": None, "path": "a.py", "line": None,
                                              "original_line": 7, "body": "Outdated"}]) +
                     json.dumps([{"path": "b.py", "subject_type": "file", "line": None, "body": "File"}]))
        self.runner.run_pass()
        text = self.record().body
        self.assertIn("unknown author on a.py line 7 (outdated)", text)
        self.assertIn("unknown author on b.py:", text)
        for absent in ("Unsubmitted", "No submission date", "None", "null"):
            self.assertNotIn(absent, text)

    def test_hostile_comments_and_repeat_replacement(self):
        hostile = "First round\n\n## Feedback\n```\n# comment\n```\n## Pull request feedback\ntext\r## Questions\n1. smuggled?"
        self.fixture("conversation", json.dumps([{"body": hostile}]))
        self.runner.run_pass()
        text = self.record().body
        for line in hostile.splitlines():
            self.assertIn("> " + line + "\n", text)
        self.assertEqual([], questions.parse(text))
        self.reset(text)
        self.fixture("conversation", '[{"body": "Second round"}]')
        self.runner.run_pass()
        text = self.record().body
        self.assertNotIn("First round", text)
        self.assertEqual(1, text.count("\n## Pull request feedback\n"))
        self.assertEqual(1, text.count("\n## Feedback\n"))

    def assert_failure(self, expected):
        before = self.story.path.read_bytes()
        self.runner.retry(self.story.id)
        self.runner.run_pass()
        self.assertEqual(before, self.story.path.read_bytes())
        self.assertEqual("rejected", self.record().metadata["step"])
        self.assertIn("FAILED", self.messages[-1])
        self.assertIn(expected, self.messages[-1])
        self.assertEqual(0, self.runner.run_pass())

    def test_endpoint_failures_and_invalid_pages(self):
        for kind, endpoint in (("reviews", "pulls/2/reviews"), ("inline", "pulls/2/comments"),
                               ("conversation", "issues/2/comments")):
            with self.subTest(kind=kind, case="exit"):
                with patch.dict(os.environ, GH_STUB_FAIL=kind):
                    self.assert_failure("stub gh: authentication failed")
            original = (self.fixtures / f"{kind}.json").read_text()
            for invalid in ("not JSON", "{}", "[1]", '[{"body": 12}]', "[] trailing", ""):
                with self.subTest(kind=kind, invalid=invalid):
                    self.fixture(kind, invalid)
                    self.assert_failure(endpoint)
            self.fixture(kind, original)

    def test_timeout_and_missing_executable(self):
        with patch.object(runner, "GH_TIMEOUT", 0.1), patch.dict(os.environ, GH_STUB_SLEEP="reviews"):
            self.assert_failure("gh api repos/acme/product/pulls/2/reviews --paginate: timed out")
        (self.bin / "gh").unlink()
        self.assert_failure("No such file or directory: 'gh'")

    def test_missing_url_never_calls_gh(self):
        for body in ("No section\n", "## Pull request\nhttps://example.com/acme/product/pull/2\n"):
            self.reset(body)
            self.assert_failure("PR URL is missing")
        self.assertFalse(self.argv.exists())

    def test_empty_feedback_and_prompt(self):
        for kind in ("reviews", "inline", "conversation"):
            self.fixture(kind, "[]")
        self.runner.run_pass()
        self.assertIn("There are no comments", self.record().body)
        step = self.repo.step(self.record())
        self.assertIn("## Pull request feedback", runner.render(step, {}))
