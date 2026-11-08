import contextlib
import io
import shutil
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

import yaml

from devteam import submission
from devteam.console import main
from devteam.steps import AgentStep, HumanStep, InvalidStep, Outcome
from devteam.yaml_format import InvalidYaml

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
            "unknown outcome": ("merge", FINDINGS, InvalidStep,
                                "'merge' is not an outcome of step 'review'; valid: approve, revise"),
            "not a mapping": ("revise", "- a finding\n", InvalidStep, "must be a mapping"),
            "sets the outcome": ("revise", "outcome: approve\n", InvalidStep, "must not set 'outcome'"),
            "duplicate key": ("revise", "findings: []\nfindings: []\n", InvalidYaml, "duplicate key 'findings'"),
            "malformed": ("revise", "findings: [\n", InvalidYaml, "not valid YAML"),
            "breaks the schema": ("revise", "findings:\n  - concern: glossary\n", InvalidStep,
                                  "does not fit its schema: findings.0: 'finding' is a required property"),
        }
        for label, (outcome, text, error, message) in cases.items():
            with self.subTest(label), self.assertRaisesRegex(error, message):
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


class CreateAndUpdateCommands(unittest.TestCase):
    def setUp(self):
        self.product = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.prefix = ["--product", str(self.product), "backlog"]

    def run_command(self, *args, stdin=""):
        with mock.patch("sys.stdin", io.StringIO(stdin)), contextlib.redirect_stdout(io.StringIO()) as output:
            main(self.prefix + list(args))
        return output.getvalue()

    def stored(self, directory, item_id):
        return yaml.safe_load((self.product / "backlog" / directory / f"{item_id}.yaml").read_text())

    def test_drafts_are_created_with_their_fields_and_requests_start_in_the_request_workflow(self):
        self.assertEqual("EPIC-001: captured\n", self.run_command("create", "epic", "Meal planning"))
        out = self.run_command("create", "story", "Filter recipes", stdin="parent: EPIC-001\noverview: As a cook\n")
        self.assertEqual("STORY-001: captured at captured\n", out)
        self.assertEqual({"id": "STORY-001", "type": "story", "title": "Filter recipes", "parent": "EPIC-001",
                          "overview": "As a cook", "workflow": "default", "step": "captured"},
                         self.stored("stories", "STORY-001"))
        self.run_command("create", "request", "Plan meals")
        self.assertEqual("request", self.stored("requests", "REQUEST-001")["workflow"])

    def test_update_replaces_fields_and_null_removes_one(self):
        self.run_command("create", "story", "Filter recipes", stdin="overview: As a cook\nscope: Search\n")
        self.assertEqual("STORY-001: updated\n", self.run_command("update", "STORY-001", stdin="scope: null\n"))
        self.assertNotIn("scope", self.stored("stories", "STORY-001"))

    def test_refused_fields_exit_with_the_reason_and_nothing_is_written(self):
        for stdin, message in (("parent: EPIC-009\n", "parent EPIC-009 is missing"),
                               ("- a list\n", "must be a YAML mapping"),
                               ("step: done\n", "the harness sets step")):
            with self.subTest(stdin), self.assertRaises(SystemExit) as exit:
                self.run_command("create", "story", "Filter recipes", stdin=stdin)
            self.assertIn(message, str(exit.exception.code))
        self.assertEqual([], list(self.product.rglob("*.yaml")))


if __name__ == "__main__":
    unittest.main()
