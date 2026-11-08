from pathlib import Path
import tempfile
import unittest

import yaml

from devteam.workflow import InvalidWorkflow, build, load
from devteam.steps import AgentStep, Check, HumanStep, PullRequest

ROLES = {"implementer"}
DEFINITION = """
initial: ready
steps:
  ready:
    owner: human
    outcomes:
      play:
        next: implement
        means: Start work on the story.
  implement:
    owner: agent:implementer
    prompt: implement.md
    outcomes:
      implemented:
        next: verify
        means: Every acceptance criterion is met and the work is committed.
  verify:
    owner: harness:Check
    outcomes:
      passed:
        next: done
        means: The project's checks pass on the branch.
      failed:
        next: implement
        means: The project's checks fail on the branch.
  done:
    owner: human
    outcomes: {}
"""


class WorkflowDefinition(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.prompts = self.directory / "prompts"
        self.prompts.mkdir()
        (self.prompts / "implement.md").write_text("Implement the story.\n")
        self.data = yaml.safe_load(DEFINITION)

    def build(self):
        return build("default", self.data, ROLES, self.prompts)

    def assertInvalid(self, message):
        with self.assertRaisesRegex(InvalidWorkflow, message):
            self.build()

    def test_a_workflow_builds_each_step_from_its_owner(self):
        workflow = self.build()
        self.assertEqual("ready", workflow.initial)
        self.assertEqual(["ready", "implement", "verify", "done"], list(workflow.steps))
        self.assertIsInstance(workflow.steps["ready"], HumanStep)
        self.assertIsInstance(workflow.steps["implement"], AgentStep)
        self.assertIsInstance(workflow.steps["verify"], Check)
        self.assertEqual({"passed": "done", "failed": "implement"}, workflow.steps["verify"].transitions)

    def test_every_outcome_leads_to_a_defined_step(self):
        self.data["steps"]["verify"]["outcomes"]["passed"]["next"] = "review"
        self.assertInvalid("step 'verify': outcome 'passed' leads to undefined step 'review'")

    def test_the_initial_step_is_defined(self):
        self.data["initial"] = "captured"
        self.assertInvalid("initial step 'captured' is not defined")

    def test_step_errors_name_the_step(self):
        del self.data["steps"]["verify"]["outcomes"]["failed"]
        self.assertInvalid("step 'verify': Check needs the outcomes 'failed'")

    def test_the_shape_of_the_workflow_is_checked(self):
        cases = {
            "not a mapping": ([], "exactly 'initial' and 'steps'"),
            "extra key": (dict(self.data, name="default"), "exactly 'initial' and 'steps'"),
            "no steps": ({"initial": "ready", "steps": {}}, "'steps' must map"),
            "steps as a list": ({"initial": "ready", "steps": ["ready"]}, "'steps' must map"),
        }
        for label, (data, message) in cases.items():
            with self.subTest(label), self.assertRaisesRegex(InvalidWorkflow, message):
                build("default", data, ROLES, self.prompts)


class LoadingWorkflows(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.prompts = self.directory / "prompts"
        self.prompts.mkdir()
        (self.prompts / "implement.md").write_text("Implement the story.\n")

    def load(self, name="default"):
        return load(name, self.directory, ROLES, self.prompts)

    def test_a_named_workflow_loads_from_its_yaml_file(self):
        (self.directory / "default.yaml").write_text(DEFINITION)
        self.assertEqual("ready", self.load().initial)

    def test_loading_errors_name_the_workflow(self):
        cases = {
            "missing": (None, "workflow 'default' is not defined"),
            "malformed": ("steps: [", "workflow 'default': "),
            "duplicate step": (DEFINITION + "  done:\n    owner: human\n    outcomes: {}\n",
                               "workflow 'default': not valid YAML: duplicate key 'done'"),
            "invalid step": (DEFINITION.replace("harness:Check", "harness:Lint"),
                             "workflow 'default': step 'verify': 'Lint' is not a harness step"),
        }
        for label, (text, message) in cases.items():
            with self.subTest(label):
                path = self.directory / "default.yaml"
                path.unlink(missing_ok=True)
                if text is not None:
                    path.write_text(text)
                with self.assertRaisesRegex(InvalidWorkflow, message):
                    self.load()

    def test_the_default_workflow_loads_against_configured_roles_and_prompts(self):
        workflow = load("default")
        self.assertEqual("captured", workflow.initial)
        self.assertIsInstance(workflow.steps["pull-request"], PullRequest)
        self.assertEqual({"merged": "merged", "rejected": "rejected", "abandon": "abandoning"},
                         workflow.steps["pull-request"].transitions)

    def test_a_workflow_name_cannot_reach_outside_the_directory(self):
        with self.assertRaisesRegex(InvalidWorkflow, "invalid workflow name '../default'"):
            self.load("../default")


if __name__ == "__main__":
    unittest.main()
