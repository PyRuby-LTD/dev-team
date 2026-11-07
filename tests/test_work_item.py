from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

from devteam.config import ROOT
from devteam.workflow import build
from devteam.steps import InvalidStep
from devteam.work_item import Backlog, InvalidWorkItem, dump, parse

WORKFLOW = """
initial: captured
steps:
  captured:
    owner: human
    outcomes:
      analyse: {next: analysis, means: Ready for analysis.}
  analysis:
    owner: agent:product_owner
    prompt: analysis.md
    output: requirements
    outcomes:
      questions: {next: answering, means: The customer must answer first.}
      analysed: {next: implement, means: Specified well enough to build.}
  answering:
    owner: human
    output: requirements
    outcomes:
      answered: {next: analysis, means: Every question has an answer.}
  implement:
    owner: agent:implementer
    prompt: implement.md
    output:
      type: object
      additionalProperties: false
      properties:
        surprises: {type: array, items: {type: string}}
    outcomes:
      implemented: {next: review, means: The code meets the criteria.}
  review:
    owner: agent:reviewer
    prompt: review.md
    output:
      type: object
      additionalProperties: false
      properties:
        findings:
          type: array
          items:
            type: object
            required: [finding]
            properties:
              finding: {type: string}
    outcomes:
      approve: {next: done, means: Every criterion is met.}
      revise: {next: implement, means: A criterion is unmet.}
  done:
    owner: human
    outcomes: {}
"""

LEVEL = "What level should the logs be written at?"
TIMING = "Should the elapsed time be captured?"


class WorkItems(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        prompts = self.root / "prompts"
        prompts.mkdir()
        for name in ("analysis", "implement", "review"):
            (prompts / f"{name}.md").write_text("Do the step.\n")
        workflow = build("default", yaml.safe_load(WORKFLOW), {"product_owner", "implementer", "reviewer"},
                              prompts)
        self.backlog = Backlog(self.root / "backlog", workflows={"default": workflow}.__getitem__)

    def stored(self, item_id):
        return yaml.safe_load(self.backlog.path(item_id).read_text())

    def test_the_example_work_item_survives_a_round_trip(self):
        example = parse((ROOT / "prompts" / "examples" / "work-item.yaml").read_text())
        self.assertEqual(example, parse(dump(example)))

    def test_capture_numbers_each_kind_and_places_it_in_the_workflow(self):
        epic = self.backlog.create("epic", "Observable API", {"overview": "Diagnose failures from logs"})
        story = self.backlog.create("story", "Log requests", {"parent": epic.id})
        second = self.backlog.create("story", "Log errors", {"parent": epic.id, "depends_on": [story.id]})
        self.assertEqual(["EPIC-001", "STORY-001", "STORY-002"], [epic.id, story.id, second.id])
        self.assertEqual({"id": "EPIC-001", "type": "epic", "title": "Observable API",
                          "overview": "Diagnose failures from logs"}, self.stored("EPIC-001"))
        self.assertEqual(("default", "captured"), (story.workflow, story.step))
        self.assertEqual(self.backlog.root / "stories" / "STORY-002.yaml", self.backlog.path(second.id))
        self.assertEqual(second, self.backlog.get("STORY-002"))

    def test_any_field_may_appear_on_any_type(self):
        task = self.backlog.create("task", "Reproduce the hang", {"steps_to_reproduce": ["Update twice"]})
        self.assertEqual(["Update twice"], self.backlog.get(task.id).steps_to_reproduce)

    def test_capture_refuses_what_the_harness_owns_and_broken_links(self):
        cases = {
            "owned field": (("story", "Log", {"step": "done"}), "the harness sets step"),
            "missing parent": (("story", "Log", {"parent": "EPIC-009"}), "parent EPIC-009 is missing"),
            "unknown type": (("feature", "Log", {}), "type must be one of"),
            "empty title": (("bug", " ", {}), "title: Value error, must be nonempty"),
            "unknown field": (("bug", "Hang", {"severity": "high"}), "severity: Extra inputs are not permitted"),
        }
        for label, (args, message) in cases.items():
            with self.subTest(label), self.assertRaisesRegex(InvalidWorkItem, message):
                self.backlog.create(*args)
        self.assertEqual([], list(self.backlog.root.rglob("*.yaml")))

    def test_update_merges_fields_and_none_removes_one(self):
        self.backlog.create("bug", "Hang", {"current_behaviour": "Hangs", "scope": "API"})
        self.backlog.update("BUG-001", {"title": "Hang on update", "scope": None, "expected_behaviour": "Saves"})
        self.assertEqual({"id": "BUG-001", "type": "bug", "title": "Hang on update", "workflow": "default",
                          "step": "captured", "current_behaviour": "Hangs", "expected_behaviour": "Saves"},
                         self.stored("BUG-001"))

    def test_a_request_lists_the_work_items_it_was_divided_into(self):
        self.backlog.create("story", "Log requests")
        self.backlog.create("bug", "Log errors", {"work_items": ["STORY-001"]})
        self.assertEqual(["STORY-001"], self.backlog.get("BUG-001").work_items)
        with self.assertRaisesRegex(InvalidWorkItem, "work item STORY-009 is missing"):
            self.backlog.update("BUG-001", {"work_items": ["STORY-001", "STORY-009"]})
        with self.assertRaisesRegex(InvalidWorkItem, "work_items: Value error, repeats an item ID"):
            self.backlog.update("BUG-001", {"work_items": ["STORY-001", "STORY-001"]})

    def test_update_leaves_step_output_and_position_to_recording(self):
        self.backlog.create("bug", "Hang")
        for fields, message in (({"step": "done"}, "the harness sets step"),
                                ({"step_outputs": []}, "the harness sets step_outputs")):
            with self.subTest(fields), self.assertRaisesRegex(InvalidWorkItem, message):
                self.backlog.update("BUG-001", fields)

    def test_update_refuses_a_dependency_cycle(self):
        self.backlog.create("bug", "First")
        self.backlog.create("bug", "Second", {"depends_on": ["BUG-001"]})
        with self.assertRaisesRegex(InvalidWorkItem, "dependency cycle: BUG-001 -> BUG-002 -> BUG-001"):
            self.backlog.update("BUG-001", {"depends_on": ["BUG-002"]})
        self.assertNotIn("depends_on", self.stored("BUG-001"))

    def played(self):
        self.backlog.create("story", "Log requests")
        self.backlog.record("STORY-001", "analyse")
        self.backlog.record("STORY-001", "analysed", {"acceptance_criteria": ["Access logs are written at INFO"]})

    def test_analysis_and_answering_write_the_requirements_and_keep_every_question(self):
        self.backlog.create("story", "Log requests", {"overview": "Capture access logs"})
        self.backlog.record("STORY-001", "analyse")
        self.backlog.record("STORY-001", "questions", {"scope": "Plain text logs today",
                                                      "questions": [{"question": LEVEL}]})
        self.backlog.record("STORY-001", "answered", {"questions": [{"question": LEVEL, "answer": "INFO"}]})
        item = self.backlog.record("STORY-001", "questions", {"questions": [{"question": TIMING}]})
        self.assertEqual(("Capture access logs", "Plain text logs today"), (item.overview, item.scope))
        self.assertEqual([(LEVEL, "INFO"), (TIMING, None)], [(q.question, q.answer) for q in item.questions])
        self.assertEqual(["captured", "analysis", "answering", "analysis"], [e.step for e in item.step_outputs])
        self.assertEqual([{"question": LEVEL}], item.step_outputs[1].output["questions"])

    def test_feedback_is_pending_for_the_step_it_leads_to_until_that_step_records(self):
        self.played()
        self.backlog.record("STORY-001", "implemented", {"surprises": ["Two log libraries"]})
        item = self.backlog.record("STORY-001", "revise", {"findings": [{"finding": "Labels should be tags"}]})
        self.assertEqual("implement", item.step)
        self.assertEqual([("review", "revise")], [(e.step, e.outcome) for e in item.pending("implement")])
        item = self.backlog.record("STORY-001", "implemented")
        self.assertEqual([], item.pending("implement"))
        self.assertEqual([("implement", "implemented")], [(e.step, e.outcome) for e in item.pending("review")])
        item = self.backlog.record("STORY-001", "approve")
        self.assertEqual(["captured", "analysis", "implement", "review", "implement", "review"],
                         [e.step for e in item.step_outputs])
        self.assertTrue(all(e.passed for e in item.step_outputs[:-1]))
        self.assertEqual(("done", False), (item.step_outputs[-1].to, item.step_outputs[-1].passed))
        self.assertEqual(item, self.backlog.get("STORY-001"))

    def test_an_outcome_the_step_lacks_is_refused_and_nothing_changes(self):
        self.backlog.create("story", "Log requests")
        before = self.backlog.path("STORY-001").read_text()
        with self.assertRaisesRegex(InvalidStep, "'analysed' is not an outcome of step 'captured'"):
            self.backlog.record("STORY-001", "analysed")
        self.assertEqual(before, self.backlog.path("STORY-001").read_text())

    def test_output_that_does_not_fit_the_step_is_refused_and_nothing_changes(self):
        self.played()
        before = self.backlog.path("STORY-001").read_text()
        cases = {
            "schema": ("implemented", {"surprises": "Two log libraries"},
                       "does not fit its schema: surprises: 'Two log libraries' is not of type 'array'"),
            "unknown field": ("implemented", {"branch": "devteam/STORY-001"},
                              "Additional properties are not allowed"),
        }
        for label, (outcome, fragment, message) in cases.items():
            with self.subTest(label), self.assertRaisesRegex(InvalidStep, message):
                self.backlog.record("STORY-001", outcome, fragment)
        with self.assertRaisesRegex(InvalidStep, "acceptance_criteria: Input should be a valid list"):
            self.backlog.create("story", "Analyse me")
            self.backlog.record("STORY-002", "analyse")
            self.backlog.record("STORY-002", "analysed", {"acceptance_criteria": "Logs at INFO"})
        self.assertEqual(before, self.backlog.path("STORY-001").read_text())

    def test_a_step_without_an_output_takes_none_but_its_outcome_is_kept(self):
        self.backlog.create("story", "Log requests")
        with self.assertRaisesRegex(InvalidStep, "step 'captured' takes no output"):
            self.backlog.record("STORY-001", "analyse", {"note": "go"})
        item = self.backlog.record("STORY-001", "analyse")
        self.assertEqual([("captured", "analyse", "analysis", {})],
                         [(e.step, e.outcome, e.to, e.output) for e in item.step_outputs])

    def test_an_epic_has_no_step_to_record(self):
        self.backlog.create("epic", "Observable API")
        with self.assertRaisesRegex(InvalidWorkItem, "EPIC-001 is not in a workflow"):
            self.backlog.record("EPIC-001", "analyse")

    def test_scan_reports_each_broken_file_and_keeps_the_rest(self):
        self.backlog.create("story", "Log requests")
        bugs = self.backlog.root / "bugs"
        bugs.mkdir()
        (bugs / "BUG-001.yaml").write_text("id: BUG-001\ntype: bug\ntitle: Hang\nparent: STORY-009\n")
        (bugs / "BUG-002.yaml").write_text("id: BUG-003\ntype: bug\ntitle: Misnamed\n")
        (bugs / "BUG-004.yaml").write_text("id: BUG-004\ntype: bug\ntitle: [\n")
        (bugs / "BUG-005.yaml").write_text("id: BUG-005\ntype: bug\ntitle: Lost\nworkflow: default\nstep: nowhere\n")
        snapshot = self.backlog.scan()
        self.assertEqual(["STORY-001"], list(snapshot.valid))
        messages = {path.name: " ".join(errors) for path, errors in snapshot.errors.items()}
        self.assertIn("parent STORY-009 is missing", messages["BUG-001.yaml"])
        self.assertIn("file name does not match id BUG-003", messages["BUG-002.yaml"])
        self.assertIn("not valid YAML", messages["BUG-004.yaml"])
        self.assertIn("'nowhere', which workflow 'default' does not define", messages["BUG-005.yaml"])

    def test_get_names_a_missing_item_or_an_id_that_is_not_one(self):
        for item_id, message in (("BUG-009", "BUG-009 does not exist"),
                                 ("PLAN-001", "'PLAN-001' is not a work-item ID")):
            with self.subTest(item_id), self.assertRaisesRegex(InvalidWorkItem, message):
                self.backlog.get(item_id)

    def test_each_write_is_committed_when_the_backlog_is_a_git_work_tree(self):
        root = self.backlog.root
        root.mkdir()
        for command in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "T"]):
            subprocess.run(["git", *command], cwd=root, check=True)
        self.backlog.create("story", "Log requests")
        self.backlog.record("STORY-001", "analyse")
        log = subprocess.run(["git", "log", "--format=%s"], cwd=root, check=True, capture_output=True, text=True)
        self.assertEqual(["STORY-001: captured analyse -> analysis", "STORY-001: captured at captured"],
                         log.stdout.splitlines())


if __name__ == "__main__":
    unittest.main()
