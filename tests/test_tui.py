import asyncio
import json
from pathlib import Path
import tempfile
import unittest

from textual.widgets import Label, Markdown, RichLog, Static, Tree

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


class Feedback(unittest.TestCase):
    def test_notes_accumulate_in_one_section_wherever_it_sits(self):
        first = questions.add_feedback("Intro.\n", "rework -> analysis", "Too big.\nSplit it.")
        self.assertEqual("Intro.\n\n## Feedback\n\n- **rework -> analysis:** Too big.\n  Split it.\n", first)
        second = questions.add_feedback(first + "\n## Review\n\nFine.\n", "revise -> implement", "Rename it")
        self.assertIn("  Split it.\n- **revise -> implement:** Rename it\n\n## Review\n\nFine.\n", second)
        self.assertEqual(1, second.count("## Feedback"))
        self.assertEqual("Intro.\n", questions.add_feedback("Intro.\n", "x", "   "))


class Acting(Fixture):
    def setUp(self):
        super().setUp()
        self.calls = []
        self.replies = []
        role = Role("analyst", "fake", "m", 5, ["fake"], "w")
        self.runner = Runner(Repository(self.repo.root, self.workflows, {"analyst"}), {"analyst": role}, self.engine,
                             lambda message: None)

    def engine(self, role, prompt, cwd, extra_dir, log, on_line=None):
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
            self.assertIsInstance(app.screen, tui.Note)
            self.assertEqual("captured", self.step(self.waiting))
            await pilot.press("escape")
            await pilot.pause()
            self.assertEqual("captured", self.step(self.waiting))
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press(*"Split", "space", *"it", "ctrl+s")
            await pilot.pause()
            self.assertEqual("analysis", self.step(self.waiting))
            self.assertTrue(self.repo.scan().valid["STORY-001"].body.endswith(
                "Some body text.\n\n## Feedback\n\n- **analyse -> analysis:** Split it\n"))
            self.assertIn("Waiting on  analyst", app.query_one("#card").content.plain)
            self.assertEqual([], self.calls)

    async def test_refresh_and_agent_reports_while_a_dialog_is_open(self):
        app = tui.Backlog(self.repo, self.runner)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            self.assertIn("enter", [binding.key for binding in app.query_one("#items").BINDINGS if binding.show])
            await pilot.press("down", "enter")
            await pilot.pause()
            self.repo.transition(self.loose.id, "analyse")
            app.action_reload()
            app.agent_report("BUG-001 analysis: analyst started")
            await pilot.pause()
            self.assertIsInstance(app.screen, tui.Actions)
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("ctrl+s")
            await pilot.pause()
            self.assertEqual("analysis", self.step(self.waiting))
            self.assertNotIn("## Feedback", self.repo.scan().valid["STORY-001"].body)
            self.assertIn("  BUG-001    analysis", " ".join(n.label.plain for n in self.nodes(app.query_one("#items"))))

    async def select(self, app, pilot, key):
        tree = app.query_one("#items")
        tree.move_cursor(next(n for n in self.nodes(tree) if n.data.key == key))
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

    async def test_finished_items_and_epics_offer_nothing(self):
        app = tui.Backlog(self.repo, self.runner)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            for key in ("STORY-003", "EPIC-002"):
                await self.select(app, pilot, key)
                self.assertEqual(1, len(app.screen_stack), key)
        self.assertEqual("done", self.step(self.finished))

    async def test_pr_decision_notes_and_harness_labels(self):
        data = json.loads((self.workflows / "default.json").read_text())
        data["steps"].update({
            "pull-request": {"owner": "human", "transitions": {"merged": "merged", "rejected": "rejected"}},
            "merged": {"owner": "harness:merged", "transitions": {"completed": "done"}},
            "rejected": {"owner": "harness:rejected", "transitions": {"completed": "analysis"}},
        })
        (self.workflows / "default.json").write_text(json.dumps(data))
        self.repo = Repository(self.repo.root, self.workflows, {"analyst"})
        self.waiting.path.write_text(self.waiting.path.read_text().replace("step: captured", "step: pull-request"))
        app = tui.Backlog(self.repo, self.runner)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await self.select(app, pilot, self.waiting.id)
            self.assertEqual(["merged", "rejected"], self.options(app))
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(1, len(app.screen_stack))
            self.assertEqual("merged", self.step(self.waiting))
            row = next(row for row in tui.rows(self.repo) if row.key == self.waiting.id)
            self.assertEqual("harness", row.waiting_on)
            self.assertFalse(row.needs_you)
            self.waiting.path.write_text(self.waiting.path.read_text().replace("step: merged", "step: pull-request"))
            app.action_reload()
            await pilot.pause()
            await self.select(app, pilot, self.waiting.id)
            await pilot.press("down", "enter")
            await pilot.pause()
            self.assertIsInstance(app.screen, tui.Note)
            labels = " ".join(str(label.content) for label in app.screen.query(Label))
            self.assertIn("Anything to record for the next steps?", labels)
            self.assertNotIn("analyst", labels)
            self.assertNotIn("implementer", labels)
            await pilot.press(*"Fix", "space", *"it", "ctrl+s")
            await pilot.pause()
            self.assertEqual("rejected", self.step(self.waiting))
            self.assertIn("**rejected -> rejected:** Fix it", self.repo.scan().valid[self.waiting.id].body)
            self.assertEqual("harness", next(row for row in tui.rows(self.repo) if row.key == self.waiting.id).waiting_on)
        self.assertEqual([], self.calls)

    async def test_customer_can_leave_a_note_on_an_agent_owned_step(self):
        app = tui.Backlog(self.repo, self.runner)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await self.select(app, pilot, "STORY-002")
            self.assertEqual(["Leave a note for the analyst", "override ready", "override back", "override questions"],
                             self.options(app))
            await pilot.press("enter")
            await pilot.pause()
            self.assertIsInstance(app.screen, tui.Note)
            await pilot.press(*"Use", "space", *"stdout", "ctrl+s")
            await pilot.pause()
            self.assertEqual(1, len(app.screen_stack))
        self.assertEqual("analysis", self.step(self.agent))
        self.assertTrue(self.repo.scan().valid["STORY-002"].body.endswith(
            "## Feedback\n\n- **note at analysis:** Use stdout\n"))
        self.assertEqual([], self.calls)

    async def test_customer_can_override_an_agent_owned_step(self):
        app = tui.Backlog(self.repo, self.runner)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await self.select(app, pilot, "STORY-002")
            await pilot.press("down", "enter")
            await pilot.pause()
            self.assertEqual(1, len(app.screen_stack))
        self.assertEqual("done", self.step(self.agent))
        self.assertEqual([], self.calls)

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
            await pilot.press("ctrl+s")
            await pilot.pause()
            self.assertEqual("analysis", self.step(self.waiting))
            self.assertEqual([], self.calls)
            await pilot.press("s")
            await self.settle(pilot, lambda: self.step(self.waiting) == "done")
            self.assertIn("**Answer:** Admins", self.calls[0] and self.repo.scan().valid["STORY-001"].body)
            await pilot.press("s")
            await self.settle(pilot, lambda: app.thread is None)

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
            await self.settle(pilot, lambda: app.thread is None)


class AgentOutput(Fixture):
    def setUp(self):
        super().setUp()
        self.lines = []
        self.code = 0
        role = Role("analyst", "fake", "m", 5, ["fake"], "w")
        self.runner = Runner(self.repo, {"analyst": role}, self.engine, lambda message: None)

    def engine(self, role, prompt, cwd, extra_dir, log, on_line=None):
        for line in self.lines:
            on_line(line)
        return self.code, "TRANSITION: ready"

    async def emit(self, lines):
        self.lines = lines
        record = self.repo.create("story", "Output", parent=self.first.id)
        record = self.repo.transition(record.id, "analyse")
        await asyncio.to_thread(self.runner.run_item, record, self.repo.step(record))

    async def test_wrapping_after_open_close_emit_open_matches_live_output(self):
        app = tui.Backlog(self.repo, self.runner)
        line = "0123456789" * 20
        async with app.run_test(size=(120, 40)) as pilot:
            output = app.query_one("#output")
            detail = app.query_one("#detail")
            column = detail.parent
            self.assertFalse(output.display)
            self.assertEqual(0, output.size.height)
            self.assertEqual([], output.lines)
            self.assertEqual(column.region.height, detail.region.height)
            await pilot.press("l")
            await pilot.pause()
            self.assertLessEqual(abs(detail.region.height - output.region.height), 1)
            self.assertEqual(column.region.height, detail.region.height + output.region.height)
            await pilot.press("l")
            await self.emit([line])
            self.assertEqual([], output.lines)
            self.assertFalse(output.display)
            await pilot.press("l")
            await pilot.pause()
            buffered = list(output.lines)
            self.assertGreater(len(buffered), 1)
            self.assertTrue(all(strip.cell_length <= output.scrollable_content_region.width for strip in buffered))
            self.assertEqual(line, "".join(strip.text for strip in buffered))
            await self.emit([line])
            await pilot.pause()
            live = output.lines[len(buffered):]
            self.assertEqual([strip.cell_length for strip in buffered], [strip.cell_length for strip in live])
            self.assertEqual(line, "".join(strip.text for strip in live))
        self.runner.on_line("after shutdown")

    async def test_hidden_buffer_is_bounded_and_preserves_order_across_runs(self):
        app = tui.Backlog(self.repo, self.runner)
        async with app.run_test(size=(120, 40)) as pilot:
            output = app.query_one("#output")
            # Before the first opening, writes must also use the bounded buffer.
            await self.emit(["first", "[red]x[/red]"])
            await self.emit(["second"])
            await pilot.press("l")
            await pilot.pause()
            self.assertEqual(["first", "[red]x[/red]", "second"], [strip.text for strip in output.lines])
            await pilot.press("l")
            previous = list(output.lines)
            await self.emit([f"line {index}" for index in range(2001)])
            self.assertEqual(previous, output.lines)
            await pilot.press("l")
            await pilot.pause()
            self.assertEqual([f"line {index}" for index in range(1, 2001)], [strip.text for strip in output.lines])

    async def run_exiting(self, lines, code):
        self.code = code
        await self.emit(lines)
        self.code = 0

    def texts(self, output):
        return [strip.text for strip in output.lines]

    async def test_output_pane_is_a_plain_log_below_detail_outside_its_scroll_content(self):
        app = tui.Backlog(self.repo, self.runner)
        async with app.run_test(size=(120, 40)):
            output = app.query_one("#output")
            detail = app.query_one("#detail")
            self.assertIsInstance(output, RichLog)
            self.assertIs(detail.parent, output.parent)
            self.assertNotIn(output, list(detail.query("*")))
            self.assertEqual(["detail", "output"], [child.id for child in output.parent.children])
            self.assertTrue(output.auto_scroll)
            self.assertEqual(2000, output.max_lines)
            self.assertFalse(output.markup)
            self.assertTrue(output.wrap)
            self.assertEqual(1, output.min_width)
            self.assertFalse(output.border_title)

    async def test_output_pane_has_the_same_border_and_padding_as_the_other_panels(self):
        app = tui.Backlog(self.repo, self.runner)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("l")
            await pilot.pause()
            output = app.query_one("#output")
            for other in (app.query_one("#detail"), app.query_one("#activity")):
                self.assertEqual(other.styles.border_top, output.styles.border_top)
                self.assertEqual(other.styles.border_bottom, output.styles.border_bottom)
                self.assertEqual(other.styles.border_left, output.styles.border_left)
                self.assertEqual(other.styles.border_right, output.styles.border_right)
                self.assertEqual(other.styles.padding, output.styles.padding)
            self.assertEqual("round", output.styles.border_top[0])

    async def test_l_toggles_the_pane_and_the_footer_names_it(self):
        bindings = [binding for binding in tui.Backlog.BINDINGS if binding[0] == "l"]
        self.assertEqual(1, len(bindings))
        self.assertIn("output", bindings[0][2].lower())
        app = tui.Backlog(self.repo, self.runner)
        async with app.run_test(size=(120, 40)) as pilot:
            output = app.query_one("#output")
            detail = app.query_one("#detail")
            column = detail.parent
            await pilot.press("l")
            await pilot.pause()
            self.assertTrue(output.display)
            self.assertLessEqual(abs(detail.region.height - output.region.height), 1)
            self.assertEqual(column.region.height, detail.region.height + output.region.height)
            await pilot.press("l")
            await pilot.pause()
            self.assertFalse(output.display)
            self.assertEqual(column.region.height, detail.region.height)

    async def test_output_log_is_not_focusable_and_tab_alternates_items_and_detail(self):
        app = tui.Backlog(self.repo, self.runner)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("l")
            await pilot.pause()
            self.assertFalse(app.query_one("#output").can_focus)
            self.assertTrue(app.query_one("#items").has_focus)
            await pilot.press("tab")
            self.assertTrue(app.query_one("#detail").has_focus)
            await pilot.press("tab")
            self.assertTrue(app.query_one("#items").has_focus)

    async def test_runs_never_change_visibility_whether_they_succeed_or_exit_non_zero(self):
        app = tui.Backlog(self.repo, self.runner)
        async with app.run_test(size=(120, 40)) as pilot:
            output = app.query_one("#output")
            await self.emit(["hidden ok"])
            self.assertFalse(output.display)
            await self.run_exiting(["hidden fail"], 3)
            self.assertFalse(output.display)
            await pilot.press("l")
            await pilot.pause()
            self.assertEqual(["hidden ok", "hidden fail"], self.texts(output))
            await self.emit(["shown ok"])
            await self.run_exiting(["shown fail"], 1)
            await pilot.pause()
            self.assertTrue(output.display)
            self.assertEqual(["hidden ok", "hidden fail", "shown ok", "shown fail"], self.texts(output))

    async def test_a_run_that_raises_leaves_the_log_and_visibility_as_they_were(self):
        def raising(role, prompt, cwd, extra_dir, log, on_line=None):
            on_line("before the crash")
            raise RuntimeError("engine crashed")
        self.runner.engine = raising
        app = tui.Backlog(self.repo, self.runner)
        async with app.run_test(size=(120, 40)) as pilot:
            output = app.query_one("#output")
            await pilot.press("l")
            await pilot.pause()
            record = self.repo.create("story", "Crash", parent=self.first.id)
            record = self.repo.transition(record.id, "analyse")
            with self.assertRaises(RuntimeError):
                await asyncio.to_thread(self.runner.run_item, record, self.repo.step(record))
            await pilot.pause()
            self.assertTrue(output.display)
            self.assertEqual(["before the crash"], self.texts(output))

    async def test_two_runs_form_one_continuous_stream_whether_the_pane_is_shown_or_hidden(self):
        app = tui.Backlog(self.repo, self.runner)
        async with app.run_test(size=(120, 40)) as pilot:
            output = app.query_one("#output")
            await self.emit(["a1", "a2"])
            await self.emit(["b1", "b2"])
            await pilot.press("l")
            await pilot.pause()
            self.assertEqual(["a1", "a2", "b1", "b2"], self.texts(output))
        app = tui.Backlog(self.repo, self.runner)
        async with app.run_test(size=(120, 40)) as pilot:
            output = app.query_one("#output")
            await pilot.press("l")
            await pilot.pause()
            await self.emit(["c1"])
            await pilot.pause()
            await self.emit(["d1"])
            await pilot.pause()
            self.assertEqual(["c1", "d1"], self.texts(output))

    async def test_brackets_in_agent_text_are_shown_literally(self):
        app = tui.Backlog(self.repo, self.runner)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("l")
            await pilot.pause()
            await self.emit(["[red]x[/red]"])
            await pilot.pause()
            self.assertEqual(["[red]x[/red]"], self.texts(app.query_one("#output")))

    async def test_runner_has_no_start_hook_and_the_tui_registers_its_listener_on_mount(self):
        self.assertFalse(hasattr(self.runner, "on_start"))
        self.assertIsNone(self.runner.on_line)
        app = tui.Backlog(self.repo, self.runner)
        async with app.run_test(size=(120, 40)):
            self.assertIsNotNone(self.runner.on_line)

    async def test_a_check_step_leaves_the_pane_untouched(self):
        (Path(self.temp.name) / "workflows" / "default.json").write_text(json.dumps({
            "initial": "captured",
            "steps": {
                "captured": {"owner": "human", "transitions": {"analyse": "analysis"}},
                "analysis": {"owner": "agent:analyst", "transitions": {"ready": "verify"}},
                "verify": {"owner": "check", "transitions": {"passed": "done", "failed": "analysis"}},
                "done": {"owner": "human", "transitions": {}},
            }}))
        checked = []

        class Checking(Runner):
            def take_checkout(self, record):
                return "devteam/" + record.id

        repo = Repository(self.repo.root, self.workflows, {"analyst"})
        runner = Checking(repo, self.runner.roles, self.engine, lambda message: None,
                          check=lambda checkout, log=None: (checked.append(1) or 0, "ok"))
        app = tui.Backlog(repo, runner)
        self.lines = ["agent line"]
        async with app.run_test(size=(120, 40)) as pilot:
            output = app.query_one("#output")
            await pilot.press("l")
            await pilot.pause()
            record = repo.create("story", "Checked", parent=self.first.id)
            record = repo.transition(record.id, "analyse")
            await asyncio.to_thread(runner.run_item, record, repo.step(record))
            await pilot.pause()
            record = repo.scan().valid[record.id]
            self.assertEqual("verify", record.metadata["step"])
            await asyncio.to_thread(runner.run_item, record, repo.step(record))
            await pilot.pause()
            self.assertEqual([1], checked)
            self.assertTrue(output.display)
            self.assertEqual(["agent line"], self.texts(output))

    def test_readme_mentions_the_l_key(self):
        readme = (Path(__file__).resolve().parent.parent / "README.md").read_text()
        self.assertIn("`l`", readme)


if __name__ == "__main__":
    unittest.main()
