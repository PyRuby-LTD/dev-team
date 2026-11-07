"""Pilot tests: the TUI opens on a backlog, and what the customer does in it reaches the harness."""
import dataclasses
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from textual.widgets import Markdown, OptionList, RichLog, TextArea

from devteam.config import load_roles
from devteam.redesign import submission
from devteam.redesign.harness import Harness
from devteam.redesign.prompt import Prompts
from devteam.redesign.tui import Answers, Console, Outcomes
from devteam.redesign.work_item import Backlog

from .test_request_journey import GIT


class Fixture(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.base = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.backlog = Backlog(self.base / "backlog", notice=lambda message: None)

    def harness(self):
        roles = {name: dataclasses.replace(role, command=[sys.executable]) for name, role in load_roles().items()}
        return Harness(Backlog(self.backlog.root, notice=lambda message: None), roles=roles, engine=self.engine,
                       report=lambda message: None)

    def engine(self, role, prompt, cwd, root, log, on_line=None):
        item = self.backlog.get(log.parent.name)
        submission.stage(root, item, self.backlog.step(item), "questions", "questions:\n  - question: Who cooks?\n")
        return 0, ""

    async def settle(self, pilot, condition):
        for _ in range(200):
            await pilot.pause(0.05)
            if condition():
                return
        self.fail("the backlog did not reach the expected state")

    async def open(self, app, pilot, item_id):
        app.select(item_id)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

    async def choose(self, app, pilot, item_id, outcome):
        await self.open(app, pilot, item_id)
        await self.pick(app, pilot, outcome)

    async def pick(self, app, pilot, outcome):
        self.assertIsInstance(app.screen, Outcomes)
        options = app.screen.query_one(OptionList)
        options.highlighted = next(i for i, option in enumerate(options.options) if option.id == outcome)
        await pilot.press("enter")
        await pilot.pause()


class Opening(Fixture):
    async def test_lists_yaml_items_under_their_epic_with_invalid_files_and_filters_to_the_customer(self):
        self.backlog.create("epic", "Meals")
        self.backlog.create("story", "Plan a week", {"parent": "EPIC-001"})
        self.backlog.record("STORY-001", "analyse")
        self.backlog.create("request", "Shopping list")
        broken = self.backlog.root / "stories" / "STORY-009.yaml"
        broken.write_text("id: nope\n")
        (self.backlog.root / "stories" / "STORY-010.md").write_text("# An original item\n")

        app = Console(self.backlog)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            self.assertEqual([("EPIC-001", 0), ("STORY-001", 1), ("REQUEST-001", 0), (str(broken), 0)],
                             [(row.key, row.depth) for row in app.shown_rows])
            rows = {row.key: row for row in app.shown_rows}
            self.assertEqual(("analysis", False), (rows["STORY-001"].step, rows["STORY-001"].needs_you))
            self.assertTrue(rows["REQUEST-001"].needs_you)
            self.assertTrue(rows[str(broken)].errors)

            await pilot.press("y")
            await pilot.pause()
            self.assertEqual(["REQUEST-001", str(broken)], [row.key for row in app.shown_rows])

    async def test_an_item_waiting_for_the_checkout_is_shown_waiting(self):
        product = self.base / "product"
        product.mkdir()
        for args in (["init", "-q", "-b", "main"], ["commit", "-q", "--allow-empty", "-m", "Start"],
                     ["switch", "-q", "-c", "devteam/STORY-002"]):
            subprocess.run(["git", "-C", str(product), *args], check=True, env={**os.environ, **GIT})
        for title in ("Plan a week", "Print the plan"):
            item = self.backlog.create("story", title)
            for outcome in ("analyse", "analysed", "sound", "play"):
                self.backlog.record(item.id, outcome)
        self.backlog.record("STORY-002", "implemented")
        harness = self.harness()
        harness.checkout = product

        app = Console(self.backlog, harness=harness)
        async with app.run_test(size=(120, 40)) as pilot:
            await self.settle(pilot, lambda: "STORY-001" in harness.waiting and "STORY-002" in harness.failed)
            app.action_reload()
            await pilot.pause()
            rows = {row.key: row for row in app.shown_rows}
            self.assertTrue(rows["STORY-001"].waiting)
            self.assertFalse(rows["STORY-002"].waiting)

    async def test_the_detail_view_is_the_detail_template(self):
        views = self.base / "views"
        views.mkdir()
        (views / "detail.md").write_text(
            "# {{ item.title }}\n\n{{ item.id }} waits at {{ step.name }} in {{ workflow.name }}"
            " with {{ pending | length }} pending\n")
        self.backlog.create("request", "Shopping list")

        app = Console(self.backlog, prompts=Prompts(views=views))
        async with app.run_test(size=(120, 40)) as pilot:
            app.select("REQUEST-001")
            await pilot.pause()
            self.assertEqual("# Shopping list\n\nREQUEST-001 waits at captured in request with 0 pending\n",
                             app.query_one("#detail-body", Markdown).source)


class Acting(Fixture):
    async def test_choosing_analyse_records_the_outcome_and_the_harness_runs_the_product_owner(self):
        self.backlog.create("request", "Shopping list")
        app = Console(self.backlog, harness=self.harness())
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await self.choose(app, pilot, "REQUEST-001", "analyse")
            await self.settle(pilot, lambda: self.backlog.get("REQUEST-001").step == "answering")
        request = self.backlog.get("REQUEST-001")
        self.assertEqual(["captured", "analysis"], [entry.step for entry in request.step_outputs])
        self.assertEqual(["Who cooks?"], [question.question for question in request.questions])

    async def test_a_running_agent_streams_its_output_to_the_screen(self):
        self.backlog.create("request", "Shopping list")
        self.backlog.record("REQUEST-001", "analyse")
        release = threading.Event()
        stub = self.engine

        def engine(role, prompt, cwd, root, log, on_line=None):
            on_line("Reading the request")
            release.wait(10)
            return stub(role, prompt, cwd, root, log)
        self.engine = engine
        app = Console(self.backlog, harness=self.harness())
        try:
            async with app.run_test(size=(120, 40)) as pilot:
                stream = app.query_one("#stream", RichLog)
                await self.settle(pilot, lambda: stream.lines)
                self.assertEqual("analysis", self.backlog.get("REQUEST-001").step)
                release.set()
                await self.settle(pilot, lambda: self.backlog.get("REQUEST-001").step == "answering")
        finally:
            release.set()

    async def test_feedback_given_with_an_outcome_is_recorded_for_the_next_step(self):
        self.backlog.create("request", "Shopping list")
        self.backlog.record("REQUEST-001", "analyse")
        self.backlog.record("REQUEST-001", "drafted")
        app = Console(self.backlog)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await self.choose(app, pilot, "REQUEST-001", "revise")
            await pilot.press(*"Split", "space", *"it", "ctrl+s")
            await self.settle(pilot, lambda: self.backlog.get("REQUEST-001").step == "analysis")
        entry = self.backlog.get("REQUEST-001").step_outputs[-1]
        self.assertEqual(("review", "revise", {"feedback": "Split it"}), (entry.step, entry.outcome, entry.output))

    async def test_every_open_question_is_answered_before_the_outcome_and_lands_on_its_question(self):
        self.backlog.create("request", "Shopping list")
        self.backlog.record("REQUEST-001", "analyse")
        self.backlog.record("REQUEST-001", "questions", {"questions": [
            {"question": "Who cooks?", "answer": "Me"}, {"question": "Which shop?"}, {"question": "Budget?"}]})
        app = Console(self.backlog)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await self.open(app, pilot, "REQUEST-001")
            self.assertIsInstance(app.screen, Answers)
            first, second = app.screen.query(TextArea)
            first.focus()
            await pilot.press(*"Aldi", "ctrl+s")
            await pilot.pause()
            self.assertIsInstance(app.screen, Answers)
            second.focus()
            await pilot.press(*"n/a", "ctrl+s")
            await pilot.pause()
            await self.pick(app, pilot, "answered")
            await self.settle(pilot, lambda: self.backlog.get("REQUEST-001").step == "analysis")
        self.assertEqual([("Who cooks?", "Me"), ("Which shop?", "Aldi"), ("Budget?", "n/a")],
                         [(question.question, question.answer) for question in self.backlog.get("REQUEST-001").questions])

    async def test_a_new_request_is_captured_from_free_text(self):
        app = Console(self.backlog)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("n")
            await pilot.pause()
            await pilot.press(*"Plan", "space", *"meals", "ctrl+s")
            await self.settle(pilot, lambda: self.backlog.path("REQUEST-001").exists())
        request = self.backlog.get("REQUEST-001")
        self.assertEqual(("Plan meals", "captured", "Plan meals"), (request.title, request.step, request.overview))


if __name__ == "__main__":
    unittest.main()
