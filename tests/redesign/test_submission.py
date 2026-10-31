import contextlib
import io
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

import yaml

from devteam.redesign import submission
from devteam.backlog import Repository
from devteam.redesign.console import main
from devteam.redesign.steps import AgentStep, HumanStep, InvalidStep, Outcome

FINDINGS = """
findings:
  - concern: glossary
    finding: Recipe shows "labels" which should be "tags".
"""


def review():
    return AgentStep("review", {"approve": Outcome("approve", "accept", "All met."),
                                "revise": Outcome("revise", "implement", "Not met.")},
                     "reviewer", Path("prompts/review.md"))


class StagingOutput(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.record = SimpleNamespace(id="BUG-001")

    def stage(self, outcome, text, step=None):
        return submission.stage(self.root, self.record, step or review(), outcome, text)

    def test_staged_output_is_taken_once(self):
        path = self.stage("revise", FINDINGS)
        self.assertEqual(self.root / "log" / "BUG-001" / "review.submission.yaml", path)
        outcome, fragment = submission.take(self.root, "BUG-001", "review")
        self.assertEqual("revise", outcome)
        self.assertEqual("glossary", fragment["findings"][0]["concern"])
        self.assertFalse(path.exists())
        self.assertIsNone(submission.take(self.root, "BUG-001", "review"))

    def test_the_last_submission_wins(self):
        self.stage("revise", FINDINGS)
        self.stage("approve", "")
        self.assertEqual(("approve", {}), submission.take(self.root, "BUG-001", "review"))
        self.assertEqual([], list(self.root.rglob("*.tmp")))

    def test_invalid_output_is_refused_and_nothing_is_staged(self):
        cases = {
            "unknown outcome": ("merge", FINDINGS, "'merge' is not an outcome of step 'review'; valid: approve, revise"),
            "not a mapping": ("revise", "- a finding\n", "must be a mapping"),
            "sets the outcome": ("revise", "outcome: approve\n", "must not set 'outcome'"),
            "duplicate key": ("revise", "findings: []\nfindings: []\n", "duplicate key 'findings'"),
            "malformed": ("revise", "findings: [\n", "not valid YAML"),
        }
        for label, (outcome, text, message) in cases.items():
            with self.subTest(label), self.assertRaisesRegex(InvalidStep, message):
                self.stage(outcome, text)
        self.assertIsNone(submission.take(self.root, "BUG-001", "review"))

    def test_only_an_agent_step_takes_a_submission(self):
        step = HumanStep("accept", {"pr": Outcome("pr", "publish", "Publish it.")})
        with self.assertRaisesRegex(InvalidStep, "BUG-001 is at step 'accept', which is not an agent step"):
            self.stage("pr", "", step)


class RecordingOutput(unittest.TestCase):
    def test_output_goes_under_the_step_name_with_its_outcome(self):
        item = {"id": "BUG-001", "challenge": {"outcome": "sound"}}
        recorded = review().record(item, "revise", yaml.safe_load(FINDINGS))
        self.assertEqual({"outcome": "sound"}, recorded["challenge"])
        self.assertEqual("revise", recorded["review"]["outcome"])
        self.assertEqual(["glossary"], [f["concern"] for f in recorded["review"]["findings"]])
        self.assertNotIn("review", item)

    def test_a_rework_replaces_the_earlier_output(self):
        first = review().record({}, "revise", yaml.safe_load(FINDINGS))
        self.assertEqual({"review": {"outcome": "approve"}}, review().record(first, "approve", {}))


class SubmitCommand(unittest.TestCase):
    def setUp(self):
        self.product = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.prefix = ["--product", str(self.product), "backlog"]
        repo = Repository(self.product / "backlog")
        repo.create("bug", "Access logs")
        for name in ("analyse", "analysed", "sound", "play", "implemented", "written", "completed", "passed"):
            repo.transition("BUG-001", name)

    def submit(self, outcome, text):
        with mock.patch("sys.stdin", io.StringIO(text)), contextlib.redirect_stdout(io.StringIO()) as output:
            main(self.prefix + ["submit", "BUG-001", outcome])
        return output.getvalue()

    def test_an_agent_submits_its_outcome_and_output(self):
        self.assertEqual("BUG-001 review: revise staged\n", self.submit("revise", FINDINGS))
        outcome, fragment = submission.take(self.product / "backlog", "BUG-001", "review")
        self.assertEqual("revise", outcome)
        self.assertEqual("glossary", fragment["findings"][0]["concern"])

    def test_a_refused_submission_exits_with_the_reason(self):
        with self.assertRaises(SystemExit) as exit:
            self.submit("merge", FINDINGS)
        self.assertIn("'merge' is not an outcome of step 'review'", str(exit.exception.code))

    def test_an_unknown_item_is_refused(self):
        with mock.patch("sys.stdin", io.StringIO("")), self.assertRaises(SystemExit) as exit:
            main(self.prefix + ["submit", "BUG-999", "approve"])
        self.assertIn("BUG-999 is missing or invalid", str(exit.exception.code))


if __name__ == "__main__":
    unittest.main()
