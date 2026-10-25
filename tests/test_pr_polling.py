"""PR polling with real repository writes and an offline gh process."""
from concurrent.futures import wait
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from devteam import runner
from devteam.backlog import Repository

ROOT = Path(__file__).resolve().parents[1]


class PullRequestPolling(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        shutil.copy(ROOT / "tests/stubs/gh", self.bin / "gh")
        (self.bin / "python3").symlink_to(sys.executable)
        self.argv = self.root / "argv.jsonl"
        self.fixtures = self.root / "fixtures"
        self.fixtures.mkdir()
        self.state("OPEN")
        env = patch.dict(os.environ, PATH=str(self.bin), GH_STUB_ARGV=str(self.argv),
                         GH_STUB_FIXTURES=str(self.fixtures), GH_STUB_FAIL="", GH_STUB_SLEEP="")
        env.start()
        self.addCleanup(env.stop)
        self.repo = Repository(self.root / "backlog")
        self.epic = self.repo.create("epic", "Epic")
        self.story = self.item()
        self.messages = []
        self.runner = runner.Runner(self.repo, report=self.messages.append)

    def item(self):
        record = self.repo.create("story", "Published", parent=self.epic.id)
        self.repo.write_body(record.id, "## Pull request\nhttps://github.com/acme/product/pull/1\n"
                             "https://github.com/acme/product/pull/2\n"
                             "## Feedback\nhttps://github.com/ignored/url/pull/3\n", "fixture")
        self.place(record, "pull-request")
        return record

    def place(self, record, step):
        current = self.repo.scan().valid[record.id]
        record.path.write_text(record.path.read_text().replace(
            f"step: {current.metadata['step']}\n", f"step: {step}\n", 1))

    def state(self, state):
        (self.fixtures / "state.json").write_text(json.dumps({"state": state, "reviewDecision": "CHANGES_REQUESTED"}))

    def calls(self):
        return [json.loads(line) for line in self.argv.read_text().splitlines()] if self.argv.exists() else []

    def poll(self, now):
        with patch.object(runner.time, "monotonic", return_value=now):
            self.runner.poll_pull_requests()

    def finish(self, now):
        futures = [future for _, future in self.runner._pr_lookups.values()]
        _, unfinished = wait(futures, timeout=5)
        self.assertFalse(unfinished)
        self.poll(now)

    def step(self):
        return self.repo.scan().valid[self.story.id].metadata["step"]

    def test_first_pass_last_url_and_silent_unmerged_states(self):
        for now, state in ((0, "OPEN"), (60, "CLOSED")):
            self.state(state)
            self.poll(now)
            self.finish(now)
            self.assertEqual("pull-request", self.step())
            self.assertEqual([], self.messages)
        self.assertEqual([["pr", "view", "https://github.com/acme/product/pull/2", "--json", "state"]] * 2,
                         self.calls())
        self.state("MERGED")
        self.poll(120)
        self.finish(120)
        self.assertEqual("merged", self.step())
        self.assertIn("pull-request: merged -> merged", self.messages[-1])
        self.assertEqual({}, self.runner.failed)

    def test_each_item_has_a_start_based_clock_on_success_and_failure(self):
        other = self.item()
        for failure in (False, True):
            with self.subTest(failure=failure), patch.dict(os.environ, GH_STUB_FAIL="state" if failure else ""):
                self.runner = runner.Runner(self.repo, report=self.messages.append)
                before = len(self.calls())
                self.poll(10)
                self.finish(20)
                self.assertEqual(before + 2, len(self.calls()))
                self.poll(69.999)
                self.assertFalse(self.runner._pr_lookups)
                self.poll(70)
                self.finish(75)
                self.assertEqual(before + 4, len(self.calls()))
                self.assertEqual({self.story.id, other.id}, set(self.runner._pr_started))

    def test_outstanding_lookup_is_not_duplicated_even_after_interval(self):
        entered, release = threading.Event(), threading.Event()

        def blocked(record):
            entered.set()
            self.assertTrue(release.wait(5))
            return "OPEN"

        with patch.object(runner, "pr_state", blocked):
            try:
                self.poll(0)
                self.assertTrue(entered.wait(2))
                original = self.runner._pr_lookups[self.story.id][1]
                self.poll(60)
                self.poll(120)
                self.assertIs(original, self.runner._pr_lookups[self.story.id][1])
            finally:
                release.set()
                self.finish(0)

    def test_manual_decisions_win_over_in_progress_results_and_errors(self):
        for decision in ("merged", "rejected"):
            for failure in (False, True):
                with self.subTest(decision=decision, failure=failure):
                    self.place(self.story, "pull-request")
                    self.runner = runner.Runner(self.repo, report=self.messages.append)
                    self.messages.clear()
                    with patch.dict(os.environ, GH_STUB_FAIL="state" if failure else ""):
                        self.state("MERGED")
                        self.poll(0)
                        self.repo.transition(self.story.id, decision)
                        self.finish(0)
                    self.assertEqual(decision, self.step())
                    self.assertEqual({}, self.runner.failed)
                    self.assertEqual([], self.messages)

    def test_failures_are_reported_once_until_success_or_changed_message(self):
        with patch.dict(os.environ, GH_STUB_FAIL="state"):
            for now in (0, 60):
                self.poll(now)
                self.finish(now)
            self.assertEqual(1, len(self.messages))
            with patch.dict(os.environ, GH_STUB_ERROR="network unavailable"):
                self.poll(120)
                self.finish(120)
            self.assertEqual(2, len(self.messages))
        self.poll(180)
        self.finish(180)
        with patch.dict(os.environ, GH_STUB_FAIL="state", GH_STUB_ERROR="network unavailable"):
            self.poll(240)
            self.finish(240)
        self.assertEqual(3, len(self.messages))
        self.assertEqual("pull-request", self.step())
        self.assertEqual({}, self.runner.failed)
        self.state("MERGED")
        self.poll(300)
        self.finish(300)
        self.assertEqual("merged", self.step())

    def test_bad_output_missing_url_executable_network_authentication_and_timeout_are_recoverable(self):
        def exercise(expected):
            self.runner = runner.Runner(self.repo, report=self.messages.append)
            self.poll(0)
            self.finish(0)
            self.assertEqual("pull-request", self.step())
            self.assertEqual({}, self.runner.failed)
            self.assertIn(expected, self.messages[-1])
            count = len(self.messages)
            self.poll(60)
            self.finish(60)
            self.assertEqual(count, len(self.messages))

        for invalid in ("", "not json", "[]", '{}', '{"state": "UNKNOWN"}', '{"state": []}'):
            with self.subTest(invalid=invalid):
                (self.fixtures / "state.json").write_text(invalid)
                exercise("invalid JSON")
        self.state("OPEN")
        for message in ("authentication required", "network unavailable"):
            with patch.dict(os.environ, GH_STUB_FAIL="state", GH_STUB_ERROR=message):
                exercise(message)
        with patch.object(runner, "GH_TIMEOUT", .05), patch.dict(os.environ, GH_STUB_SLEEP="state"):
            exercise("timed out")
        (self.bin / "gh").rename(self.bin / "gh-disabled")
        exercise("No such file or directory")
        self.repo.write_body(self.story.id, "No PR section", "fixture")
        before = self.calls()
        exercise("PR URL is missing")
        self.assertEqual(before, self.calls())

    def test_other_steps_failed_items_and_unsupported_custom_steps_are_not_queried(self):
        for step in self.repo.workflow("default").steps:
            if step == "pull-request":
                continue
            self.place(self.story, step)
            self.poll(0)
            self.assertFalse(self.runner._pr_lookups)
        self.place(self.story, "pull-request")
        self.runner._failed[self.story.id] = "previous failure"
        self.poll(0)
        self.assertFalse(self.runner._pr_lookups)
        self.runner.retry(self.story.id)
        step = self.repo.step(self.repo.scan().valid[self.story.id])
        del step.transitions["merged"]
        self.poll(0)
        self.assertFalse(self.runner._pr_lookups)
        self.assertEqual([], self.calls())

    def test_once_never_queries_github_and_returns_at_pull_request(self):
        self.state("MERGED")
        self.runner.run(once=True)
        self.assertEqual("pull-request", self.step())
        self.assertEqual([], self.calls())
        self.assertEqual([], self.messages)
