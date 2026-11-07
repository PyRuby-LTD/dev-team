"""Choosing standards at ready: the customer's choice replaces the item's standards for every later step."""
import unittest

from devteam.redesign.template import load_standards

from .test_default_journey import SOUND
from .test_implement_journey import implemented
from .test_review_journey import APPROVE
from .test_verify_journey import WRITTEN, Synced

ANALYSED = """$DEV_TEAM backlog submit STORY-001 analysed <<'OUTPUT'
acceptance_criteria:
  - A week of meals can be planned
standards:
  - name: quality
    reason: The cook's journey changes
  - name: technical-writing
    reason: The plan is printed for the cook
OUTPUT
"""


class StandardsAtReady(Synced):
    def at_ready(self, *steps):
        self.script({"sh": ANALYSED}, {"sh": SOUND}, *({"sh": sh} for sh in steps))
        self.ok("backlog", "create", "story", "Plan a week", stdin="overview: As a cook, I want to plan a week.\n")
        self.ok("backlog", "record", "STORY-001", "analyse")
        self.ok("run", "--once")
        self.assertEqual("ready", self.story("STORY-001").step)

    def test_playing_with_one_standard_added_and_one_removed_replaces_the_items_standards(self):
        self.at_ready(implemented("STORY-001", "planner.txt"), WRITTEN, APPROVE)

        self.ok("backlog", "record", "STORY-001", "play", stdin="standards: [technical-writing, api-contracts]\n")
        self.ok("run", "--once")

        story = self.story("STORY-001")
        self.assertEqual("accept", story.step)
        self.assertEqual([("technical-writing", "The plan is printed for the cook"),
                          ("api-contracts", "chosen by the customer")],
                         [(standard.name, standard.reason) for standard in story.standards])
        available = load_standards()
        prompts = [path.read_text() for path in sorted(self.prompts.glob("*.txt"))[2:]]
        self.assertEqual(3, len(prompts), "expected the implementer, tester and reviewer prompts")
        for prompt in prompts:
            self.assertIn(available["technical-writing"].body, prompt)
            self.assertIn(available["api-contracts"].body, prompt)
            self.assertNotIn(available["quality"].body, prompt)

    def test_a_standard_that_does_not_exist_is_refused_and_the_item_stays_at_ready(self):
        self.at_ready()

        result = self.dev_team("backlog", "record", "STORY-001", "play", stdin="standards: [security]\n")

        self.assertNotEqual(0, result.returncode)
        self.assertIn("security", result.stderr)
        story = self.story("STORY-001")
        self.assertEqual("ready", story.step)
        self.assertEqual(["quality", "technical-writing"], [standard.name for standard in story.standards])


if __name__ == "__main__":
    unittest.main()
