from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import tempfile
from typing import ClassVar
import unittest
from unittest import mock

import yaml

from devteam import runner as original
from devteam.check import Result
from devteam.redesign import steps
from devteam.redesign.steps import (Abandon, AgentStep, Check, HarnessStep, HumanStep, InvalidStep, Merged,
                           Outcome, PullRequest, Rejected, Step, StepFailed, Sync, Waiting, build)

DEFINITION = """
accept:
  owner: human
  outcomes:
    pr:
      next: publish
      means: The change is what you wanted; publish it as a pull request.
    revise:
      next: implement
      means: The change needs more work; say what in the item before choosing this.
implement:
  owner: agent:implementer
  prompt: implement.md
  outcomes:
    implemented:
      next: test
      means: Every acceptance criterion is met and the work is committed.
done:
  owner: human
  outcomes: {}
"""
ROLES = {"implementer"}


class FakeHarness:
    def __init__(self, branch):
        self.roles = {"implementer": SimpleNamespace(branch=branch)}


class StepDefinitions(unittest.TestCase):
    def setUp(self):
        self.prompts = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (self.prompts / "implement.md").write_text("Implement the story.\n")
        self.specs = yaml.safe_load(DEFINITION)

    def build(self, name):
        return build(name, self.specs[name], ROLES, self.prompts)

    def assertInvalid(self, name, message):
        with self.assertRaisesRegex(InvalidStep, message):
            self.build(name)

    def test_outcomes_carry_their_next_step_and_meaning(self):
        step = self.build("accept")
        self.assertIsInstance(step, HumanStep)
        self.assertEqual(Outcome("pr", "publish", "The change is what you wanted; publish it as a pull request."),
                         step.outcomes["pr"])
        self.assertEqual({"pr": "publish", "revise": "implement"}, step.transitions)

    def test_an_agent_step_uses_the_prompt_its_definition_names(self):
        step = self.build("implement")
        self.assertIsInstance(step, AgentStep)
        self.assertEqual("implementer", step.role)
        self.assertEqual((self.prompts / "implement.md").resolve(), step.prompt)

    def test_steps_may_share_a_prompt(self):
        self.specs["resolve"] = dict(self.specs["implement"])
        self.assertEqual(self.build("implement").prompt, self.build("resolve").prompt)

    def test_an_agent_step_needs_an_existing_prompt_inside_the_prompts_directory(self):
        cases = {
            "no prompt": (None, "must have exactly 'outcomes', 'owner', 'prompt'"),
            "blank prompt": ("", "'prompt' must name a file"),
            "missing file": ("absent.md", r"prompt .*absent\.md does not exist"),
            "escapes the directory": ("../implement.md", "is outside"),
        }
        for label, (prompt, message) in cases.items():
            with self.subTest(label):
                spec = dict(self.specs["implement"])
                if prompt is None:
                    del spec["prompt"]
                else:
                    spec["prompt"] = prompt
                with self.assertRaisesRegex(InvalidStep, message):
                    build("implement", spec, ROLES, self.prompts)

    def test_a_human_step_has_no_prompt(self):
        self.specs["accept"]["prompt"] = "implement.md"
        self.assertInvalid("accept", "must have exactly 'outcomes', 'owner'")

    def test_a_step_may_name_its_output(self):
        schema = {"type": "object", "properties": {"feedback": {"type": "string"}}}
        for output in (schema, "requirements"):
            with self.subTest(output):
                self.specs["accept"]["output"] = output
                self.assertEqual(output, self.build("accept").output)
        del self.specs["accept"]["output"]
        self.assertIsNone(self.build("accept").output)

    def test_an_output_must_be_requirements_or_a_valid_schema(self):
        for output, message in (("findings", "'output' must be 'requirements' or a JSON Schema"),
                                ({"type": "dictionary"}, "'output' is not a valid JSON Schema")):
            with self.subTest(output):
                self.specs["accept"]["output"] = output
                self.assertInvalid("accept", message)

    def test_an_agent_role_must_be_configured(self):
        self.specs["implement"]["owner"] = "agent:wizard"
        self.assertInvalid("implement", "'wizard' is not in config/roles.toml")

    def test_malformed_definitions_are_rejected(self):
        cases = {
            "transitions instead of outcomes": ({"owner": "human", "transitions": {}}, "must have exactly 'outcomes', 'owner'"),
            "no owner": ({"outcomes": {}}, "must have an 'owner'"),
            "outcome without meaning": ({"owner": "human", "outcomes": {"pr": {"next": "publish"}}},
                                        "'pr' must have exactly 'next' and 'means'"),
            "blank meaning": ({"owner": "human", "outcomes": {"pr": {"next": "publish", "means": "  "}}},
                              "'pr' must say what it means"),
            "missing next": ({"owner": "human", "outcomes": {"pr": {"next": "", "means": "x"}}},
                             "'pr' must name the next step"),
            "outcomes as a list": ({"owner": "human", "outcomes": ["pr"]}, "must map each name"),
            "unknown owner": ({"owner": "robot:Sync", "outcomes": {}}, "owner must be"),
        }
        for label, (spec, message) in cases.items():
            with self.subTest(label), self.assertRaisesRegex(InvalidStep, message):
                build("accept", spec, ROLES, self.prompts)


KINDS = (Check, Rejected, Sync, Merged, Abandon, PullRequest)


def outcomes(*names):
    return {name: Outcome(name, "done", f"{name} happened.") for name in names}


def spec(owner, *names):
    return {"owner": owner, "outcomes": {name: {"next": "done", "means": "x"} for name in names}}


class ActionStepDefinitions(unittest.TestCase):
    def test_every_action_builds_from_its_class_name(self):
        for cls in KINDS:
            owner = f"{cls.kind}:{cls.__name__}"
            with self.subTest(owner):
                step = build("step", spec(owner, *cls.produces), ROLES)
                self.assertIsInstance(step, cls)
                self.assertEqual(owner, step.owner)

    def test_the_owner_names_a_harness_step_of_the_right_kind(self):
        cases = {
            "unknown class": ("git:Rebase", "'Rebase' is not a harness step in devteam.redesign.steps"),
            "grouping": ("git:GitStep", "'GitStep' is not a harness step"),
            "base": ("harness:HarnessStep", "'HarnessStep' is not a harness step"),
            "not a step": ("harness:Outcome", "'Outcome' is not a harness step"),
            "not a class": ("harness:build", "'build' is not a harness step"),
            "wrong kind": ("harness:Sync", "Sync is a git step, so its owner is 'git:Sync'"),
            "project step": ("git:myproject.steps.Deploy", "steps from 'myproject.steps' are not supported yet"),
        }
        for label, (owner, message) in cases.items():
            with self.subTest(label), self.assertRaisesRegex(InvalidStep, message):
                build("step", spec(owner, "completed"), ROLES)

    def test_a_new_harness_step_needs_only_its_subclass(self):
        @dataclass
        class Notify(HarnessStep):
            produces: ClassVar[frozenset] = frozenset({"sent"})

        with mock.patch.object(steps, "Notify", Notify, create=True):
            step = build("notify", spec("harness:Notify", "sent"), ROLES)
        self.assertIsInstance(step, Notify)

    def test_an_action_needs_every_outcome_it_produces(self):
        with self.assertRaisesRegex(InvalidStep, "Sync needs the outcomes 'conflicted'"):
            build("sync", spec("git:Sync", "completed"), ROLES)

    def test_the_customer_may_add_outcomes_of_their_own(self):
        spec = {"owner": "git:PullRequest", "outcomes": {
            "merged": {"next": "merged", "means": "GitHub reports the pull request merged."},
            "abandon": {"next": "abandoning", "means": "Give up on the change."}}}
        self.assertEqual({"merged": "merged", "abandon": "abandoning"}, build("pull-request", spec, ROLES).transitions)

    def test_an_action_has_no_prompt(self):
        definition = dict(spec("harness:Check", "passed", "failed"), prompt="verify.md")
        with self.assertRaisesRegex(InvalidStep, "must have exactly 'outcomes', 'owner'"):
            build("verify", definition, ROLES)


class ActionSteps(unittest.TestCase):
    def test_actions_are_dispatched_and_labelled_by_their_kind(self):
        self.assertEqual("harness", Check("verify", outcomes("passed", "failed")).label())
        self.assertEqual("git", Sync("sync", outcomes("completed", "conflicted")).label())
        self.assertEqual("finished", Merged("merged", {}).label())
        for cls in KINDS:
            self.assertTrue(cls.automatic)

    def test_only_steps_that_work_on_the_branch_use_the_checkout(self):
        harness = FakeHarness(branch=False)
        using = {cls for cls in KINDS if cls("step", {}).uses_checkout(harness)}
        self.assertEqual({Check, Sync, Merged, Abandon}, using)

    def test_git_steps_return_the_outcome_without_output(self):
        for cls, action in ((Merged, "merged"), (Abandon, "abandon"), (Rejected, "rejected")):
            with self.subTest(action), mock.patch.object(original, action, return_value="completed") as performed:
                self.assertEqual(("completed", {}), cls("step", {}).perform("harness", "item", "log"))
                performed.assert_called_once_with("harness", "item")

    def test_a_git_step_that_cannot_run_yet_waits_and_one_that_cannot_run_fails(self):
        with mock.patch.object(original, "merged", side_effect=original.Waiting("held")):
            with self.assertRaisesRegex(Waiting, "held"):
                Merged("merged", {}).perform("harness", "item", "log")
        with mock.patch.object(original, "merged", side_effect=original.StepFailed("broken")):
            with self.assertRaisesRegex(StepFailed, "broken"):
                Merged("merged", {}).perform("harness", "item", "log")

    def test_a_check_that_did_not_finish_has_failed(self):
        step = Check("verify", outcomes("passed", "failed"))
        for code, status in ((0, "finished"), (124, "timed out"), (127, "could not be started")):
            with self.subTest(status):
                checked = SimpleNamespace(checkout="checkout",
                                          check=mock.Mock(return_value=Result(code, "output", status)))
                outcome, output = step.perform(checked, "item", "log")
                self.assertEqual("passed" if status == "finished" else "failed", outcome)
                self.assertEqual({"summary"}, set(output))
                checked.check.assert_called_once_with("checkout", log="log")
        with self.assertRaisesRegex(StepFailed, "needs a git repository"):
            step.perform(SimpleNamespace(checkout=None), "item", "log")

    def test_a_pull_request_waits_until_github_reports_it_merged(self):
        step = PullRequest("pull-request", outcomes("merged"))
        for state in ("OPEN", "CLOSED"):
            with self.subTest(state), mock.patch.object(original, "pr_state", return_value=state):
                with self.assertRaisesRegex(Waiting, f"the pull request is {state.lower()}"):
                    step.perform("harness", "item", "log")
        with mock.patch.object(original, "pr_state", return_value="MERGED"):
            self.assertEqual(("merged", {}), step.perform("harness", "item", "log"))


class HumanSteps(unittest.TestCase):
    def test_a_human_step_waits_for_you_and_is_never_dispatched(self):
        step = HumanStep("accept", {"pr": Outcome("pr", "publish", "Publish it.")})
        self.assertEqual("human", step.owner)
        self.assertFalse(step.automatic)
        self.assertTrue(step.needs_you)
        self.assertEqual("YOU", step.label())
        self.assertFalse(step.uses_checkout(FakeHarness(branch=True)))
        with self.assertRaises(NotImplementedError):
            step.perform(FakeHarness(branch=True), "item", "log")

    def test_a_step_without_outcomes_is_finished(self):
        step = HumanStep("done", {})
        self.assertTrue(step.terminal)
        self.assertFalse(step.needs_you)
        self.assertEqual("finished", step.label())


class AgentSteps(unittest.TestCase):
    def step(self):
        return AgentStep("implement", {"implemented": Outcome("implemented", "test", "Done.")},
                         "implementer", Path("prompts/implement.md"))

    def test_an_agent_step_is_dispatched_and_labelled_by_its_role(self):
        step = self.step()
        self.assertEqual("agent:implementer", step.owner)
        self.assertTrue(step.automatic)
        self.assertFalse(step.needs_you)
        self.assertEqual("implementer", step.label())
        self.assertIsNone(step.produces)

    def test_checkout_use_follows_the_role_configuration(self):
        self.assertTrue(self.step().uses_checkout(FakeHarness(branch=True)))
        self.assertFalse(self.step().uses_checkout(FakeHarness(branch=False)))


class BaseStep(unittest.TestCase):
    def test_the_base_step_has_no_owner_of_its_own(self):
        with self.assertRaises(NotImplementedError):
            Step("x", {}).owner


if __name__ == "__main__":
    unittest.main()
