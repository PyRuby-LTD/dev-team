import json
from pathlib import Path
import tempfile
import unittest

from textual.widgets import Markdown, Static, Tree

from devteam import tui
from devteam.backlog import Repository

WORKFLOW = {
    "initial": "captured",
    "steps": {
        "captured": {"owner": "human", "transitions": {"analyse": "analysis"}},
        "analysis": {"owner": "agent:analyst", "transitions": {"ready": "done", "back": "captured"}},
        "done": {"owner": "human", "transitions": {}},
    },
}


class Fixture(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        workflows = Path(self.temp.name) / "workflows"
        workflows.mkdir()
        (workflows / "default.json").write_text(json.dumps(WORKFLOW))
        self.repo = Repository(Path(self.temp.name) / "backlog", workflows, {"analyst"})
        self.first = self.repo.create("epic", "First epic")
        self.second = self.repo.create("epic", "Second epic")
        self.waiting = self.repo.create("story", "Needs me", "# Heading\n\nSome body text.\n", parent=self.first.id)
        self.agent = self.repo.create("story", "With the analyst", parent=self.second.id)
        self.finished = self.repo.create("story", "Finished", parent=self.first.id)
        self.task = self.repo.create("task", "A task", parent=self.waiting.id)
        self.loose = self.repo.create("bug", "Loose bug")
        self.repo.transition(self.agent.id, "analyse")
        self.repo.transition(self.finished.id, "analyse")
        self.repo.transition(self.finished.id, "ready")

    def by_key(self):
        return {row.key: row for row in tui.rows(self.repo)}


class ViewModel(Fixture):
    def test_items_are_grouped_under_their_epic_with_step_and_owner(self):
        data = tui.rows(self.repo)
        self.assertEqual(
            [("EPIC-001", 0), ("STORY-001", 1), ("TASK-001", 2), ("STORY-003", 1), ("EPIC-002", 0), ("STORY-002", 1), ("BUG-001", 0)],
            [(row.key, row.depth) for row in data])
        rows = self.by_key()
        self.assertEqual(("captured", "YOU", True), (rows["STORY-001"].step, rows["STORY-001"].waiting_on, rows["STORY-001"].needs_you))
        self.assertEqual(("analysis", "analyst", False), (rows["STORY-002"].step, rows["STORY-002"].waiting_on, rows["STORY-002"].needs_you))
        self.assertEqual(("done", "", False), (rows["STORY-003"].step, rows["STORY-003"].waiting_on, rows["STORY-003"].needs_you))
        self.assertEqual("", rows["EPIC-001"].step)
        self.assertEqual(" 3 waiting on you   1 with agents  1 finished  5 items", tui.summary(data).plain)

    def test_owners_are_distinguishable_by_text_alone(self):
        rows = self.by_key()
        self.assertEqual("* STORY-001  captured   Needs me", tui.item_label(rows["STORY-001"]).plain)
        self.assertEqual("  STORY-002  analysis   With the analyst", tui.item_label(rows["STORY-002"]).plain)
        self.assertEqual("  STORY-003  done       Finished", tui.item_label(rows["STORY-003"]).plain)
        self.assertEqual("EPIC-001  First epic  (2 waiting on you)", tui.item_label(rows["EPIC-001"], 2).plain)
        self.assertIn("Waiting on  YOU", tui.card(rows["STORY-001"]).plain)
        self.assertIn("Waiting on  analyst", tui.card(rows["STORY-002"]).plain)
        self.assertIn("this item is finished", tui.card(rows["STORY-003"]).plain)
        self.assertIn("Next        analyse -> analysis", tui.card(rows["STORY-001"]).plain)

    def test_filter_keeps_items_waiting_on_you_and_their_ancestors(self):
        shown = [row.key for row in tui.visible(tui.rows(self.repo), True)]
        self.assertEqual(["EPIC-001", "STORY-001", "TASK-001", "BUG-001"], shown)

    def test_invalid_file_is_listed_with_its_error_and_others_remain(self):
        self.agent.path.write_text("---\nid: STORY-002\n---\n")
        data = tui.rows(self.repo)
        invalid = data[-1]
        self.assertEqual(("stories/STORY-002.md", "INVALID"), (invalid.label, invalid.step))
        self.assertIn("STORY-001", [row.key for row in data])
        self.assertIn("1 invalid", tui.summary(data).plain)
        self.assertIn("ERROR: missing required fields", tui.card(invalid).plain)
        self.assertTrue(tui.item_label(invalid).plain.startswith("! stories/STORY-002.md"))


class Screen(Fixture):
    def labels(self, app):
        found = []

        def walk(node, depth):
            for child in node.children:
                found.append((depth, child.label.plain))
                walk(child, depth + 1)
        walk(app.query_one("#items", Tree).root, 0)
        return found

    def card(self, app):
        return app.query_one("#card", Static).content.plain

    async def test_browse_read_filter_group_and_refresh(self):
        app = tui.Backlog(self.repo)
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            self.assertEqual([
                (0, "EPIC-001  First epic  (2 waiting on you)"),
                (1, "* STORY-001  captured   Needs me"),
                (2, "* TASK-001   captured   A task"),
                (1, "  STORY-003  done       Finished"),
                (0, "EPIC-002  Second epic"),
                (1, "  STORY-002  analysis   With the analyst"),
                (0, "* BUG-001    captured   Loose bug"),
            ], self.labels(app))
            self.assertIn("3 waiting on you", app.query_one("#summary", Static).content.plain)
            self.assertTrue(self.card(app).startswith("EPIC-001  First epic"))

            await pilot.press("down")
            await pilot.pause()
            self.assertIn("STORY-001  Needs me", self.card(app))
            self.assertIn("Step        captured", self.card(app))
            self.assertIn("Some body text.", app.query_one("#body", Markdown).source)

            self.waiting.path.write_text(self.waiting.path.read_text().replace("step: captured", "step: analysis"))
            app.action_reload()
            await pilot.pause()
            self.assertIn((1, "  STORY-001  analysis   Needs me"), self.labels(app))
            self.assertIn("Waiting on  analyst", self.card(app))
            self.assertEqual("STORY-001", app.query_one("#items", Tree).cursor_node.data.key)

            await pilot.press("y")
            await pilot.pause()
            self.assertEqual(["EPIC-001  First epic  (1 waiting on you)", "* TASK-001   captured   A task",
                              "* BUG-001    captured   Loose bug"],
                             [label for _, label in self.labels(app) if "STORY-001" not in label])
            await pilot.press("y", "g")
            await pilot.pause()
            self.assertEqual(["captured  (2)  YOU", "analysis  (2)  analyst", "done  (1)  finished"],
                             [label for depth, label in self.labels(app) if depth == 0])

            await pilot.press("tab")
            self.assertTrue(app.query_one("#detail").has_focus)
            await pilot.press("tab")
            self.assertTrue(app.query_one("#items", Tree).has_focus)

    async def test_invalid_file_is_shown_and_the_rest_stay_usable(self):
        self.agent.path.write_text("broken")
        app = tui.Backlog(self.repo)
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            labels = [label for _, label in self.labels(app)]
            self.assertTrue(any(label.startswith("! stories/STORY-002.md") for label in labels))
            self.assertIn("* STORY-001  captured   Needs me", labels)
            await pilot.press("end")
            await pilot.pause()
            self.assertIn("ERROR:", self.card(app))


if __name__ == "__main__":
    unittest.main()
