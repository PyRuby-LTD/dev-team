import contextlib
import io
import shutil
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

import yaml

from devteam.redesign import submission
from devteam.redesign.console import main
from devteam.redesign.steps import AgentStep, HumanStep, InvalidStep, Outcome

FIXTURES = Path(__file__).parent / "fixtures"

FINDINGS = """
findings:
  - concern: glossary
    finding: Recipe shows "labels" which should be "tags".
    outcome: fix
"""


FINDINGS_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {"findings": {
    "type": "array", "items": {"type": "object", "required": ["concern", "finding"]}}}}


def review():
    return AgentStep("review", {"approve": Outcome("approve", "accept", "All met."),
                                "revise": Outcome("revise", "implement", "Not met.")},
                     "reviewer", Path("prompts/review.md"), output=FINDINGS_SCHEMA)


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
            "breaks the schema": ("revise", "findings:\n  - concern: glossary\n",
                                  "does not fit its schema: findings.0: 'finding' is a required property"),
        }
        for label, (outcome, text, message) in cases.items():
            with self.subTest(label), self.assertRaisesRegex(InvalidStep, message):
                self.stage(outcome, text)
        self.assertIsNone(submission.take(self.root, "BUG-001", "review"))

    def test_only_an_agent_step_takes_a_submission(self):
        step = HumanStep("accept", {"pr": Outcome("pr", "publish", "Publish it.")})
        with self.assertRaisesRegex(InvalidStep, "BUG-001 is at step 'accept', which is not an agent step"):
            self.stage("pr", "", step)


class SubmitCommand(unittest.TestCase):
    def setUp(self):
        self.product = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.prefix = ["--product", str(self.product), "backlog"]
        bugs = self.product / "backlog" / "bugs"
        bugs.mkdir(parents=True)
        shutil.copy(FIXTURES / "BUG-001.yaml", bugs)

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
        self.assertIn("BUG-999 does not exist", str(exit.exception.code))


if __name__ == "__main__":
    unittest.main()
