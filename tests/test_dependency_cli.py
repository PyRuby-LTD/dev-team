"""STORY-024: a story waits for the stories it depends on, and starts once the customer releases it.

The real `dev-team` command line is used throughout: the customer captures a story that depends on another,
plays it, and the runner holds it back; clearing the dependency lets the same story start.
"""
from tests.test_run_evidence import Product


class DependentStoryFromTheCommandLine(Product):
    def branches(self):
        return self.git(self.product, "branch", "--list", "devteam/STORY-002").strip()

    def test_story_is_held_until_its_dependency_is_cleared_and_then_starts(self):
        self.devteam("backlog", "capture", "story", "Second", "--id", "STORY-002", "--parent", "EPIC-001",
                     "--depends-on", "STORY-001")
        for transition in ("analyse", "analysed", "sound", "play"):
            self.devteam("backlog", "move", "STORY-002", transition)
        self.assertIn("STORY-001", self.text(self.backlog / "stories" / "STORY-002.md"))

        held = self.run_once()

        self.assertIn("waiting for STORY-001", held)
        self.assertEqual("", self.branches())
        self.assertFalse(self.prompts.exists() and list(self.prompts.glob("*.txt")))

        self.devteam("backlog", "depends-on", "STORY-002")
        self.plan({"reply": "implemented"})
        self.run_once()

        self.assertNotEqual("", self.branches())
        self.assertTrue(list(self.prompts.glob("*.txt")))
