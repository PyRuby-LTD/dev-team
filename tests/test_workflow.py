import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from devteam.backlog import InvalidRecord, Repository
from devteam.cli import main
from devteam.workflow import InvalidWorkflow, build, load

ROLES = {"analyst", "implementer", "reviewer"}


def definition():
    return {
        "initial": "captured",
        "steps": {
            "captured": {"owner": "human", "transitions": {"analyse": "analysis"}},
            "analysis": {"owner": "agent:analyst", "transitions": {"ready": "done", "back": "captured"}},
            "done": {"owner": "human", "transitions": {}},
        },
    }


class WorkflowDefinition(unittest.TestCase):
    def test_default_workflow_loads_against_configured_roles(self):
        workflow = load("default")
        self.assertEqual("captured", workflow.initial)
        for step in workflow.steps.values():
            self.assertTrue(step.human or step.check or step.harness or step.role)
            self.assertLessEqual(set(step.transitions.values()), set(workflow.steps))
        self.assertEqual("analyst", workflow.steps["analysis"].role)
        # Implementation cannot reach review without passing the tester; a stuck implementer has a way out.
        self.assertEqual({"implemented": "test", "blocked": "ready"}, workflow.steps["implement"].transitions)
        self.assertEqual({"written": "verify", "defect": "implement"}, workflow.steps["test"].transitions)
        # Only the harness's own run of the suite lets an item reach review.
        self.assertTrue(workflow.steps["verify"].check)
        self.assertEqual({"passed": "review", "failed": "test"}, workflow.steps["verify"].transitions)
        self.assertEqual(["verify"], [n for n, s in workflow.steps.items() if "review" in s.transitions.values()])
        self.assertEqual("tester", workflow.steps["test"].role)
        # Analysis cannot reach the customer's play decision without passing the challenger.
        self.assertEqual({"answering", "challenge"}, set(workflow.steps["analysis"].transitions.values()))
        self.assertEqual("challenger", workflow.steps["challenge"].role)
        self.assertEqual({"sound": "ready", "rework": "analysis"}, workflow.steps["challenge"].transitions)
        self.assertIsNone(workflow.steps["ready"].role)
        self.assertTrue(workflow.steps["done"].terminal)

    def test_pr_decision_gates_completion_after_publish(self):
        steps = load("default").steps
        self.assertEqual({"published": "pull-request"}, steps["publish"].transitions)
        self.assertTrue(steps["pull-request"].human)
        self.assertEqual({"merged": "merged", "rejected": "rejected"}, steps["pull-request"].transitions)
        self.assertEqual({"accept": "done", "pr": "publish", "revise": "implement"}, steps["accept"].transitions)
        for action, target in (("merged", "done"), ("rejected", "implement")):
            self.assertTrue(steps[action].harness)
            self.assertIsNone(steps[action].role)
            self.assertEqual(action, steps[action].action)
            self.assertEqual({"completed": target}, steps[action].transitions)

    def test_invalid_harness_actions_and_outcomes_name_the_step(self):
        for owner, transitions, reason in (
            ("harness:unknown", {"completed": "done"}, "unknown harness action"),
            ("harness:merged", {}, "exactly the transition 'completed'"),
            ("harness:rejected", {"completed": "done", "failed": "captured"}, "exactly the transition 'completed'"),
            ("harness:merged", {"ready": "done"}, "exactly the transition 'completed'"),
        ):
            with self.subTest(owner=owner, transitions=transitions):
                data = definition()
                data["steps"]["analysis"] = {"owner": owner, "transitions": transitions}
                with self.assertRaises(InvalidWorkflow) as raised:
                    build("w", data, ROLES)
                self.assertIn("step 'analysis'", str(raised.exception))
                self.assertIn(reason, str(raised.exception))

    def test_invalid_definitions_name_the_step(self):
        def change(mutate):
            data = definition()
            mutate(data)
            return data
        cases = {
            "no owner": (change(lambda d: d["steps"]["analysis"].pop("owner")), "'analysis'"),
            "two owners": (change(lambda d: d["steps"]["analysis"].update(owner=["agent:analyst", "human"])), "'analysis'"),
            "extra key": (change(lambda d: d["steps"]["analysis"].update(collaborators=[])), "'analysis'"),
            "bad owner": (change(lambda d: d["steps"]["analysis"].update(owner="analyst")), "'analysis'"),
            "unknown target": (change(lambda d: d["steps"]["captured"]["transitions"].update(go="nowhere")), "'captured'"),
            "unknown role": (change(lambda d: d["steps"]["analysis"].update(owner="agent:wizard")), "'wizard'"),
            "unknown initial": (change(lambda d: d.update(initial="start")), "'start'"),
            "no steps": ({"initial": "a", "steps": {}}, "steps"),
            "check with other outcomes": (change(lambda d: d["steps"]["analysis"].update(owner="check")), "'passed' and 'failed'"),
        }
        for name, (data, expected) in cases.items():
            with self.subTest(case=name), self.assertRaises(InvalidWorkflow) as raised:
                build("w", data, ROLES)
            self.assertIn(expected, str(raised.exception))

    def test_missing_malformed_and_duplicate_step_files(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "broken.json").write_text("{")
            Path(directory, "twice.json").write_text(
                '{"initial": "a", "steps": {"a": {"owner": "human", "transitions": {}},'
                ' "a": {"owner": "human", "transitions": {}}}}')
            for name in ("absent", "broken", "twice", "../escape"):
                with self.subTest(name=name), self.assertRaises(InvalidWorkflow):
                    load(name, directory, ROLES)


class ItemSteps(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "backlog"
        self.workflows = Path(self.temp.name) / "workflows"
        self.workflows.mkdir()
        data = definition()
        data["initial"] = "analysis"
        (self.workflows / "default.json").write_text(json.dumps(data))
        self.repo = Repository(self.root, self.workflows, ROLES)
        self.epic = self.repo.create("epic", "An epic")
        self.story = self.repo.create("story", "A story", "\r\nBody --- text  \r\n", parent=self.epic.id)

    def test_capture_uses_the_workflow_initial_step(self):
        self.assertEqual("analysis", self.story.metadata["step"])

    def test_undefined_workflow_or_step_is_reported_and_not_actionable(self):
        original = self.story.path.read_text()
        for field, expected in (("workflow: default", "workflow: absent"), ("step: analysis", "step: nowhere")):
            with self.subTest(field=field):
                self.story.path.write_text(original.replace(field, expected))
                snapshot = self.repo.scan()
                self.assertIn(self.story.path, snapshot.errors)
                self.assertNotIn(self.story.id, snapshot.valid)
                with self.assertRaises(InvalidRecord):
                    self.repo.transition(self.story.id, "ready")

    def test_transition_changes_only_the_step_line(self):
        text = '---\nid: STORY-001\ntype: story\ntitle: "Quoted: title"\nparent: EPIC-001\nworkflow: default\nstep: analysis\n---\n\r\nBody\r\n---\nstep: analysis\n'
        self.story.path.write_bytes(text.encode())
        updated = self.repo.transition(self.story.id, "ready")
        self.assertEqual("done", updated.metadata["step"])
        self.assertEqual(text.replace("step: analysis\n---", "step: done\n---", 1), self.story.path.read_bytes().decode())
        self.assertEqual([], list(self.root.rglob("*.tmp")))

    def test_invalid_transition_is_refused_and_file_untouched(self):
        before = self.story.path.read_bytes()
        for name in ("analyse", "done", "nonsense"):
            with self.subTest(name=name), self.assertRaises(InvalidRecord):
                self.repo.transition(self.story.id, name)
        with self.assertRaises(InvalidRecord):
            self.repo.transition(self.epic.id, "ready")
        self.repo.transition(self.story.id, "ready")
        after = self.story.path.read_bytes()
        with self.assertRaises(InvalidRecord) as raised:
            self.repo.transition(self.story.id, "ready")
        self.assertIn("terminal", str(raised.exception))
        self.assertNotEqual(before, after)
        self.assertEqual(after, self.story.path.read_bytes())

    def test_cli_move_and_validate_show_step_and_owner(self):
        prefix = ["--product", str(Path(self.temp.name) / "cli"), "backlog"]
        with contextlib.redirect_stdout(io.StringIO()) as output:
            main(prefix + ["capture", "bug", "CLI bug"])
            main(prefix + ["move", "BUG-001", "analyse"])
            main(prefix + ["validate"])
        self.assertIn("BUG-001 -> analysis (agent:analyst)", output.getvalue())
        self.assertRegex(output.getvalue(), r"BUG-001\s+analysis\s+agent:analyst\s+CLI bug")
        with self.assertRaises(SystemExit) as exit:
            main(prefix + ["move", "BUG-001", "play"])
        self.assertIn("not a transition", str(exit.exception.code))


if __name__ == "__main__":
    unittest.main()
