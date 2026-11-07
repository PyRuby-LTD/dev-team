import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from devteam.config import ROOT
from devteam.redesign import flow
from devteam.redesign.console import main
from devteam.redesign.prompt import RUN_VALUES, InvalidPrompt, Prompts
from devteam.redesign.steps import AgentStep, HumanStep, Outcome
from devteam.redesign.work_item import WorkItem, parse

SNIPPET = """\
{% if item.questions %}
## Questions

{{ item.questions | yaml }}
{% endif %}
{% for entry in pending %}
## Feedback from {{ entry.step }}

{{ entry.output | yaml }}
{% endfor %}
{% include "_standards.md" %}
"""

STANDARD = """\
---
name: {name}
kind: rule
description: The {name} rule
---
Follow the {name} rule.
"""


def implement():
    return {"implemented": Outcome("implemented", "review", "The code meets the criteria."),
            "blocked": Outcome("blocked", "ready", "The customer must decide.")}


class RenderingPrompts(unittest.TestCase):
    def setUp(self):
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.prompts_dir = directory / "prompts"
        self.prompts_dir.mkdir()
        for name in ("_submit.md", "_standards.md"):
            (self.prompts_dir / name).write_text((ROOT / "prompts" / name).read_text())
        (self.prompts_dir / "implement.md").write_text(SNIPPET)
        standards = directory / "standards"
        standards.mkdir()
        for name in ("api-contracts", "quality", "platform"):
            (standards / f"{name}.md").write_text(STANDARD.format(name=name))
        self.prompts = Prompts(self.prompts_dir, standards)
        self.step = AgentStep("implement", implement(), "implementer", self.prompts_dir / "implement.md",
                              output={"type": "object", "properties": {"surprises": {"type": "array"}}})

    def item(self, **fields):
        return WorkItem.model_validate({"id": "STORY-001", "type": "story", "title": "Log requests",
                                        "workflow": "default", "step": "implement", **fields})

    def test_questions_and_pending_feedback_are_given_as_yaml(self):
        item = self.item(
            questions=[{"question": "Which level?", "answer": "INFO"}],
            step_outputs=[{"step": "review", "outcome": "revise", "to": "implement", "passed": True,
                           "output": {"findings": [{"finding": "Old finding"}]}},
                          {"step": "review", "outcome": "revise", "to": "implement",
                           "output": {"findings": [{"finding": "Labels should be tags"}]}}])
        text = self.prompts.render(item, self.step)
        self.assertIn("## Questions\n\n- question: Which level?\n  answer: INFO\n", text)
        self.assertIn("## Feedback from review\n\nfindings:\n  - finding: Labels should be tags\n", text)
        self.assertNotIn("Old finding", text)

    def test_the_customers_choice_of_standards_wins_over_analysis(self):
        proposed = [{"name": "api-contracts", "reason": "Paths"}, {"name": "quality", "reason": "Journeys"}]
        text = self.prompts.render(self.item(standards=proposed), self.step)
        self.assertEqual(["api-contracts", "quality"], self.standards_in(text))
        played = self.item(standards=proposed, step_outputs=[
            {"step": "ready", "outcome": "play", "to": "implement", "output": {"standards": ["platform"]}}])
        self.assertEqual(["platform"], self.standards_in(self.prompts.render(played, self.step)))

    def standards_in(self, text):
        return [line.split()[2] for line in text.splitlines() if line.startswith("## Standard:")]

    def test_an_unknown_standard_is_refused(self):
        item = self.item(standards=[{"name": "security", "reason": "Auth"}])
        with self.assertRaisesRegex(InvalidPrompt, "STORY-001 names standards that do not exist: security"):
            self.prompts.render(item, self.step)

    def test_a_name_the_context_lacks_fails_and_is_named(self):
        (self.prompts_dir / "implement.md").write_text("Work on {{ branch }}.\n")
        with self.assertRaisesRegex(InvalidPrompt, "'branch' is undefined"):
            self.prompts.render(self.item(), self.step)
        self.assertIn("Work on devteam/STORY-001.", self.prompts.render(self.item(), self.step,
                                                                        {"branch": "devteam/STORY-001"}))

    def test_the_submit_instructions_give_the_outcomes_and_the_output_schema(self):
        text = self.prompts.render(self.item(), self.step)
        self.assertIn("backlog submit STORY-001 <outcome>", text)
        self.assertIn("- `blocked`: The customer must decide.\n", text)
        self.assertIn("```yaml\ntype: object\nproperties:\n  surprises:\n    type: array\n```", text)

    def test_only_an_agent_step_has_a_prompt(self):
        with self.assertRaisesRegex(InvalidPrompt, "step 'ready' is not an agent step"):
            self.prompts.render(self.item(), HumanStep("ready", implement()))


class DefaultPrompts(unittest.TestCase):
    def test_every_agent_step_in_the_default_workflow_renders_for_the_example_item(self):
        item = parse((ROOT / "prompts" / "examples" / "work-item.yaml").read_text())
        prompts = Prompts()
        values = {name: f"<{name}>" for name in RUN_VALUES}
        steps = [step for step in flow.load("default").steps.values() if isinstance(step, AgentStep)]
        self.assertTrue(steps)
        for step in steps:
            with self.subTest(step.name):
                self.assertIn(f"backlog submit {item.id}", prompts.render(item, step, values))


class PromptCommand(unittest.TestCase):
    def preview(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            main(["prompt", *args])
        return output.getvalue()

    def test_one_step_is_previewed_with_its_brief_and_run_values(self):
        text = self.preview("review", "--set", "branch=devteam/STORY-NNN")
        self.assertTrue(text.startswith("==== review: agent:reviewer ====\n"))
        self.assertIn("---- system prompt (roles/reviewer.md) ----", text)
        self.assertIn("---- prompt (prompts/review.md) ----", text)
        self.assertIn("devteam/STORY-NNN", text)
        self.assertIn("<checkout>", text)

    def test_every_agent_step_is_previewed_without_a_step(self):
        headers = [line for line in self.preview().splitlines() if line.startswith("==== ")]
        self.assertIn("==== implement: agent:implementer ====", headers)
        self.assertIn("==== publish: agent:publisher ====", headers)

    def test_an_item_is_previewed_from_the_products_backlog(self):
        product = Path(self.enterContext(tempfile.TemporaryDirectory()))
        tasks = product / "backlog" / "tasks"
        tasks.mkdir(parents=True)
        (tasks / "TASK-001.yaml").write_text("id: TASK-001\ntype: task\ntitle: Extract InputWidget\n"
                                             "workflow: default\nstep: analysis\nchange: Add InputWidget\n")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            main(["--product", str(product), "prompt", "analysis", "--item", "TASK-001"])
        self.assertIn("## The task: Extract InputWidget", output.getvalue())
        self.assertIn("## Example task", output.getvalue())

    def test_a_request_is_analysed_through_every_lens_and_sees_its_drafts(self):
        product = Path(self.enterContext(tempfile.TemporaryDirectory()))
        backlog = product / "backlog"
        (backlog / "stories").mkdir(parents=True)
        (backlog / "requests").mkdir()
        (backlog / "stories" / "STORY-001.yaml").write_text("id: STORY-001\ntype: story\ntitle: Filter recipes\n"
                                                             "workflow: default\nstep: captured\n")
        (backlog / "requests" / "REQUEST-001.yaml").write_text(
            "id: REQUEST-001\ntype: request\ntitle: Plan meals\nworkflow: request\nstep: analysis\n"
            "overview: Let families plan meals\nwork_items: [STORY-001]\n"
            "step_outputs:\n  - {step: review, outcome: revise, to: analysis, output: {feedback: Split search}}\n")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            main(["--product", str(product), "prompt", "analysis", "--item", "REQUEST-001"])
        text = output.getvalue()
        self.assertIn("---- prompt (prompts/analysis/product-owner.md) ----", text)
        self.assertIn("## The request: Plan meals", text)
        self.assertIn("## Sent back by review (revise)\n\n~~~yaml\nfeedback: Split search\n~~~", text)
        self.assertIn("## Drafts\n\n~~~yaml\nid: STORY-001\n", text)
        for heading in ("## Lens: architect", "## Lens: platform", "## Lens: quality", "## Rule: api-contracts"):
            self.assertIn(heading, text)
        self.assertIn("backlog create <type>", text)
        self.assertIn("- `drafted`: ", text)

    def test_a_step_without_a_prompt_is_refused(self):
        with self.assertRaises(SystemExit) as exit:
            self.preview("sync")
        self.assertIn("step 'sync' is not an agent step", str(exit.exception.code))


if __name__ == "__main__":
    unittest.main()
