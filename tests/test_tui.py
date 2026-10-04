import json
from pathlib import Path
import tempfile
import unittest

from textual.widgets import Markdown, Static, Tree

from devteam import questions, tui
from devteam.backlog import Repository
from devteam.config import Role
from devteam.runner import Runner

WORKFLOW = {
    "initial": "captured",
    "steps": {
        "captured": {"owner": "human", "transitions": {"analyse": "analysis"}},
        "analysis": {"owner": "agent:analyst", "transitions": {"ready": "done", "back": "captured", "questions": "answering"}},
        "answering": {"owner": "human", "transitions": {"answered": "analysis", "withdraw": "done"}},
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
        self.workflows = workflows
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
        self.assertEqual((("analyse", "analysis", "analyst"),), rows["STORY-001"].transitions)
        self.assertIn(("ready", "done", "finished"), rows["STORY-002"].transitions)

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


BODY = """Intro.

## Questions

1. Which users
   are affected?

   **Answer:** Admins.
2. What is the deadline?
- Any budget?

## Notes

1. Not a question.
"""


class QuestionParsing(unittest.TestCase):
    def test_questions_are_list_items_under_the_heading_and_answers_mark_them(self):
        found = questions.parse(BODY)
        self.assertEqual([("Which users are affected?", True), ("What is the deadline?", False), ("Any budget?", False)],
                         [(q.text, q.answered) for q in found])
        self.assertEqual([], questions.parse("No questions here.\n1. Nor this.\n"))

    def test_answers_are_written_beneath_their_questions_only(self):
        updated = questions.answer(BODY, {0: "ignored, already answered", 1: "Friday.\nNo later.", 2: "  "})
        self.assertIn("2. What is the deadline?\n\n   **Answer:** Friday.\n   No later.\n- Any budget?\n", updated)
        self.assertEqual(BODY.count("Admins."), updated.count("Admins."))
        self.assertNotIn("ignored", updated)
        self.assertEqual([True, True, False], [q.answered for q in questions.parse(updated)])
        self.assertTrue(updated.endswith("1. Not a question.\n"))
        windows = questions.answer(BODY.replace("\n", "\r\n"), {2: "None."})
        self.assertIn("- Any budget?\r\n\r\n   **Answer:** None.\r\n", windows)


class Acting(Fixture):
    def setUp(self):
        super().setUp()
        self.calls = []
        self.replies = []
        role = Role("analyst", "fake", "m", 5, ["fake"], "w")
        self.runner = Runner(Repository(self.repo.root, self.workflows, {"analyst"}), {"analyst": role}, self.engine,
                             lambda message: None)

    def engine(self, role, prompt, cwd, extra_dir, log):
        self.calls.append(prompt)
        log.write_text("transcript")
        return self.replies.pop(0)

    def step(self, record):
        return self.repo.scan().valid[record.id].metadata["step"]

    def options(self, app):
        return [str(option.prompt).split("  ")[0] for option in app.screen.query_one("OptionList").options]

    async def settle(self, pilot, condition):
        for _ in range(100):
            await pilot.pause(0.05)
            if condition():
                return
        self.fail("the screen did not reach the expected state")

    async def test_human_step_offers_exactly_its_transitions_and_moves_the_item(self):
        app = tui.Backlog(self.repo, self.runner)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("down", "enter")
            await pilot.pause()
            self.assertIsInstance(app.screen, tui.Actions)
            self.assertEqual(["analyse"], self.options(app))
            await pilot.press("q", "escape")
            await pilot.pause()
            self.assertEqual(1, len(app.screen_stack))
            self.assertEqual("captured", self.step(self.waiting))
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual("analysis", self.step(self.waiting))
            self.assertIn("Waiting on  analyst", app.query_one("#card").content.plain)
            self.assertEqual([], self.calls)

    async def test_agent_owned_and_finished_items_offer_nothing(self):
        app = tui.Backlog(self.repo, self.runner)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            tree = app.query_one("#items")
            for key in ("STORY-002", "STORY-003", "EPIC-002"):
                node = next(n for n in self.nodes(tree) if n.data.key == key)
                tree.move_cursor(node)
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(1, len(app.screen_stack), key)
        self.assertEqual(("analysis", "done"), (self.step(self.agent), self.step(self.finished)))

    def nodes(self, tree):
        found, pending = [], list(tree.root.children)
        while pending:
            node = pending.pop()
            found.append(node)
            pending.extend(node.children)
        return found

    async def test_answering_questions_then_moving_on_and_the_agent_resumes(self):
        self.repo.transition(self.waiting.id, "analyse")
        self.repo.write_body(self.waiting.id, "Intro.\n\n## Questions\n\n1. Which users?\n2. What deadline?\n", "questions")
        self.repo.transition(self.waiting.id, "questions")
        self.replies = [(0, "TRANSITION: ready")]
        app = tui.Backlog(self.repo, self.runner)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()
            self.assertIn("2 unanswered questions", app.query_one("#card").content.plain)
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(["Answer 2 questions", "answered", "withdraw"], self.options(app))
            await pilot.press("enter")
            await pilot.pause()
            self.assertIsInstance(app.screen, tui.Answers)
            await pilot.press(*"Admins")
            await pilot.press("tab")
            await pilot.press(*"Friday")
            await pilot.press("ctrl+s")
            await pilot.pause()
            body = self.repo.scan().valid["STORY-001"].body
            self.assertIn("1. Which users?\n\n   **Answer:** Admins\n2. What deadline?\n\n   **Answer:** Friday\n", body)
            self.assertEqual("answering", self.step(self.waiting))
            self.assertIsInstance(app.screen, tui.Actions)
            self.assertEqual(["answered", "withdraw"], self.options(app))
            await pilot.press("s")
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual("analysis", self.step(self.waiting))
            self.assertEqual([], self.calls)
            await pilot.press("s")
            await self.settle(pilot, lambda: self.step(self.waiting) == "done")
            self.assertIn("**Answer:** Admins", self.calls[0] and self.repo.scan().valid["STORY-001"].body)
            await pilot.press("s")

    async def test_failed_agent_is_shown_and_can_be_retried(self):
        self.repo.transition(self.waiting.id, "analyse")
        self.replies = [(2, ""), (0, "TRANSITION: ready"), (0, "TRANSITION: ready")]
        app = tui.Backlog(self.repo, self.runner)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("down", "s")
            await self.settle(pilot, lambda: "STORY-001" in self.runner.failed and self.step(self.agent) == "done")
            await pilot.pause(0.1)
            card = app.query_one("#card").content.plain
            self.assertIn("The agent failed: exit 2", card)
            self.assertEqual("analysis", self.step(self.waiting))
            await pilot.press("t")
            await self.settle(pilot, lambda: self.step(self.waiting) == "done")
            await pilot.press("s")


if __name__ == "__main__":
    unittest.main()
