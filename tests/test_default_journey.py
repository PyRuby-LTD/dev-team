"""The default workflow's first group, analysis, challenge and ready, driven through the dev-team commands."""
import unittest

from tests.journey import Product, submit

QUESTION = submit("questions", "questions:\n  - question: Which days does a week start on?\n")

ANALYSED = submit("analysed", """acceptance_criteria:
  - A week of meals can be planned from Monday
standards:
  - name: quality
    reason: The cook's journey changes
""")

REWORK = submit("rework", """findings:
  - concern: Ambiguous criteria
    finding: The criterion does not say how many meals a day are planned.
""")

REANALYSED = submit("analysed", "acceptance_criteria:\n  - A week of meals can be planned from Monday, with three meals a day\n")

SOUND = submit("sound", "findings: []\n")


class AnalysisChallengeReady(Product):
    def story(self):
        return self.item("stories", "STORY-001")

    def capture_and_analyse(self):
        self.team.create("story", "Plan a week", "overview: As a cook, I want to plan a week.\n")
        self.team.record("STORY-001", "analyse")

    def test_a_story_is_analysed_answered_challenged_reworked_and_waits_at_ready(self):
        self.script(QUESTION, ANALYSED, REWORK, REANALYSED, SOUND)
        self.capture_and_analyse()

        self.run_once()
        self.assertEqual("answering", self.story().step)
        self.team.record("STORY-001", "answered",
                         "questions:\n  - question: Which days does a week start on?\n    answer: Monday.\n")

        self.run_once()
        story = self.story()
        self.assertEqual("ready", story.step)
        self.assertEqual(["A week of meals can be planned from Monday, with three meals a day"],
                         story.acceptance_criteria)
        self.assertEqual("Monday.", story.questions[0].answer)
        self.assertEqual(["quality"], [standard.name for standard in story.standards])
        self.assertEqual([("captured", "analyse", "analysis"), ("analysis", "questions", "answering"),
                          ("answering", "answered", "analysis"), ("analysis", "analysed", "challenge"),
                          ("challenge", "rework", "analysis"), ("analysis", "analysed", "challenge"),
                          ("challenge", "sound", "ready")],
                         [(entry.step, entry.outcome, entry.to) for entry in story.step_outputs])

        seen = self.seen(4).item
        self.assertEqual([("challenge", "rework", "The criterion does not say how many meals a day are planned.")],
                         [(entry.step, entry.outcome, finding["finding"])
                          for entry in seen.pending("analysis") for finding in entry.output["findings"]])

        for step in ("analysis", "challenge"):
            with self.subTest(step=step):
                self.previewable(step, "STORY-001")

    def test_the_customer_sends_a_story_at_ready_back_to_analysis_with_feedback(self):
        self.script(ANALYSED, SOUND)
        self.capture_and_analyse()
        self.run_once()
        self.assertEqual("ready", self.story().step)

        self.team.record("STORY-001", "rework", "feedback: Plan weekends separately.\n")
        story = self.story()
        self.assertEqual("analysis", story.step)
        self.assertEqual([{"feedback": "Plan weekends separately."}],
                         [entry.output for entry in story.pending("analysis")])


if __name__ == "__main__":
    unittest.main()
