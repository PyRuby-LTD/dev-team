"""The default workflow's first group, analysis, challenge and ready, driven through the dev-team command."""
import unittest

from devteam.redesign.work_item import parse

from .test_request_journey import Product

QUESTION = """$DEV_TEAM backlog submit STORY-001 questions <<'OUTPUT'
questions:
  - question: Which days does a week start on?
OUTPUT
"""

ANALYSED = """$DEV_TEAM backlog submit STORY-001 analysed <<'OUTPUT'
acceptance_criteria:
  - A week of meals can be planned from Monday
standards:
  - name: quality
    reason: The cook's journey changes
OUTPUT
"""

REWORK = """$DEV_TEAM backlog submit STORY-001 rework <<'OUTPUT'
findings:
  - concern: Ambiguous criteria
    finding: The criterion does not say how many meals a day are planned.
OUTPUT
"""

REANALYSED = """python3 -c 'import os, shutil; shutil.copy("backlog/stories/STORY-001.yaml", os.environ["STUB_PROMPTS"] + "/item-seen-by-second-analysis.yaml")'
$DEV_TEAM backlog submit STORY-001 analysed <<'OUTPUT'
acceptance_criteria:
  - A week of meals can be planned from Monday, with three meals a day
OUTPUT
"""

SOUND = """$DEV_TEAM backlog submit STORY-001 sound <<'OUTPUT'
findings: []
OUTPUT
"""


class AnalysisChallengeReady(Product):
    def story(self):
        return self.item("stories", "STORY-001")

    def capture_and_analyse(self):
        self.ok("backlog", "create", "story", "Plan a week", stdin="overview: As a cook, I want to plan a week.\n")
        self.ok("backlog", "record", "STORY-001", "analyse")

    def test_a_story_is_analysed_answered_challenged_reworked_and_waits_at_ready(self):
        self.script({"sh": QUESTION}, {"sh": ANALYSED}, {"sh": REWORK}, {"sh": REANALYSED}, {"sh": SOUND})
        self.capture_and_analyse()

        self.ok("run", "--once")
        self.assertEqual("answering", self.story().step)
        self.ok("backlog", "record", "STORY-001", "answered",
                stdin="questions:\n  - question: Which days does a week start on?\n    answer: Monday.\n")

        self.ok("run", "--once")
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

        seen = parse((self.prompts / "item-seen-by-second-analysis.yaml").read_text())
        self.assertEqual([("challenge", "rework", "The criterion does not say how many meals a day are planned.")],
                         [(entry.step, entry.outcome, finding["finding"])
                          for entry in seen.pending("analysis") for finding in entry.output["findings"]])

        for step in ("analysis", "challenge"):
            with self.subTest(step=step):
                self.assertTrue(self.ok("prompt", step, "--item", "STORY-001").stdout.strip())

    def test_the_customer_sends_a_story_at_ready_back_to_analysis_with_feedback(self):
        self.script({"sh": ANALYSED}, {"sh": SOUND})
        self.capture_and_analyse()
        self.ok("run", "--once")
        self.assertEqual("ready", self.story().step)

        self.ok("backlog", "record", "STORY-001", "rework", stdin="feedback: Plan weekends separately.\n")
        story = self.story()
        self.assertEqual("analysis", story.step)
        self.assertEqual([{"feedback": "Plan weekends separately."}],
                         [entry.output for entry in story.pending("analysis")])


if __name__ == "__main__":
    unittest.main()
