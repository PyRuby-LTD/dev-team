"""The request workflow driven through the dev-team commands, with the agents following a script."""
import os
import shutil
import unittest
from unittest.mock import patch

from devteam import engines
from devteam.config import load_roles

from tests.journey import Product, nothing, submit

QUESTIONS = submit("questions", "questions:\n  - question: Who plans the meals?\n")


def drafts(agent):
    agent.attempt("divided", "work_items: [EPIC-001]\n")
    agent.create("epic", "Meal planning", "overview: Plan a week of meals.\n")
    agent.create("story", "Plan a week", "parent: EPIC-001\noverview: As a cook, I want to plan a week of meals.\n")
    agent.submit("drafted", "work_items: [EPIC-001, STORY-001]\n")


class RequestJourney(Product):
    def test_a_request_is_analysed_into_a_question_answered_and_divided_into_drafts(self):
        self.script(QUESTIONS, drafts)
        self.capture_and_analyse()
        self.assertEqual("analysis", self.request().step)

        self.run_once()
        self.assertEqual("answering", self.request().step)
        self.assertEqual(["Who plans the meals?"], [q.question for q in self.request().questions])

        self.team.record("REQUEST-001", "answered",
                         "questions:\n  - question: Who plans the meals?\n    answer: The household cook.\n")
        self.assertEqual("analysis", self.request().step)

        self.run_once()
        [refusal] = self.seen(2).refusals
        self.assertTrue(refusal.strip(), "the refusal gave no reasons")
        request = self.request()
        self.assertEqual("review", request.step)
        self.assertEqual(["EPIC-001", "STORY-001"], request.work_items)
        self.assertEqual("drafted", request.step_outputs[-1].outcome)

        self.team.record("REQUEST-001", "approve")
        self.assertEqual("done", self.request().step)
        self.assertEqual("The household cook.", self.request().questions[0].answer)
        story = self.item("stories", "STORY-001")
        self.assertEqual(("default", "captured", "EPIC-001"), (story.workflow, story.step, story.parent))
        self.assertIsNone(self.item("epics", "EPIC-001").step)
        self.assertEqual("", self.git("status", "--porcelain", cwd=self.product / "backlog"))


def three_drafts(agent):
    agent.create("epic", "Meal planning", "overview: Plan a week of meals.\n")
    agent.create("story", "Plan a week", "parent: EPIC-001\noverview: As a cook, I want to plan a week of meals.\n")
    agent.create("story", "Print the plan", "parent: EPIC-001\noverview: As a cook, I want to print my plan.\n")
    agent.submit("drafted", "work_items: [EPIC-001, STORY-001, STORY-002]\n")


def revised_drafts(agent):
    agent.update("STORY-001", "overview: As a cook, I want to plan a week of meals and print it.\n")
    agent.submit("drafted", "work_items: [EPIC-001, STORY-001]\n"
                            "dropped:\n  - id: STORY-002\n    reason: Printing is now part of planning a week.\n")


class RevisingDrafts(Product):
    def test_a_revised_request_updates_one_draft_and_drops_another_which_the_customer_marks_wont_fix(self):
        self.script(three_drafts, revised_drafts)
        self.capture_and_analyse()
        self.run_once()
        self.assertEqual("review", self.request().step)

        self.team.record("REQUEST-001", "revise", "feedback: Printing belongs with planning.\n")
        self.run_once()
        request = self.request()
        self.assertEqual("review", request.step)
        self.assertEqual(["EPIC-001", "STORY-001"], request.work_items)
        self.assertEqual([("STORY-002", "Printing is now part of planning a week.")],
                         [(drop.id, drop.reason) for drop in request.dropped])
        self.assertIn("print", self.item("stories", "STORY-001").overview)

        self.team.record("REQUEST-001", "approve")
        self.team.record("STORY-002", "wontfix")
        dropped = self.item("stories", "STORY-002")
        self.assertEqual("wontfix", dropped.step)
        self.assertEqual([("captured", "wontfix", "wontfix")],
                         [(entry.step, entry.outcome, entry.to) for entry in dropped.step_outputs])
        self.refused(self.team.record, "STORY-002", "analyse")


class AgentFailures(Product):
    def assertStillAtAnalysis(self, failed):
        self.assertEqual(["REQUEST-001"], list(failed))
        request = self.request()
        self.assertEqual("analysis", request.step)
        self.assertEqual(["captured"], [entry.step for entry in request.step_outputs])

    def test_an_agent_that_exits_without_submitting_leaves_the_item_at_its_step(self):
        self.script(nothing)
        self.capture_and_analyse()
        self.assertStillAtAnalysis(self.run_failing())
        self.assertEqual(1, len(self.agent.agents), "the engine did not run")

    def test_an_engine_exiting_with_an_error_leaves_the_item_at_its_step_despite_a_submission(self):
        self.script(lambda agent: QUESTIONS(agent) or 3)
        self.capture_and_analyse()
        self.assertStillAtAnalysis(self.run_failing())
        self.assertEqual(1, len(self.agent.agents), "the engine did not run")

    def test_a_missing_engine_command_is_reported_and_the_item_stays_at_its_step(self):
        self.team = self.dev_team(self.product, engine=engines.run)
        command = load_roles()["product_owner"].command[0]
        self.capture_and_analyse()
        tools = self.base / "no-engines"
        tools.mkdir()
        (tools / "git").symlink_to(shutil.which("git"))
        with patch.dict(os.environ, {"PATH": str(tools)}):
            failed = self.run_failing()
        self.assertStillAtAnalysis(failed)
        self.assertIn(command, failed["REQUEST-001"])


class CustomerOutcomes(Product):
    def test_an_item_at_ready_can_be_marked_wont_fix(self):
        self.script(submit("analysed", "acceptance_criteria: [A week of meals can be planned]\n"), submit("sound"))
        self.team.create("story", "Plan a week", "overview: As a cook, I want to plan a week.\n")
        self.team.record("STORY-001", "analyse")
        self.run_once()
        self.assertEqual("ready", self.item("stories", "STORY-001").step)
        self.team.record("STORY-001", "wontfix")
        self.assertEqual("wontfix", self.item("stories", "STORY-001").step)

    def test_invalid_output_is_refused_with_reasons_and_the_item_is_unchanged(self):
        self.team.create("request", "Plan meals")
        path = self.product / "backlog" / "requests" / "REQUEST-001.yaml"
        before = path.read_bytes()
        for outcome, output in (("analyse", "feedback: Go\n"), ("finish", ""), ("analyse", "- a list\n")):
            with self.subTest(outcome=outcome, output=output):
                self.assertTrue(self.refused(self.team.record, "REQUEST-001", outcome, output).strip(),
                                "no reason given")
        self.assertEqual(before, path.read_bytes())

    def test_an_agent_step_is_not_recorded_as_the_customer(self):
        self.capture_and_analyse()
        self.refused(self.team.record, "REQUEST-001", "questions", "questions: []\n")
        self.assertEqual("analysis", self.request().step)


if __name__ == "__main__":
    unittest.main()
