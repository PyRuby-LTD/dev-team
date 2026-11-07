"""Steps that do not hold the checkout run alongside each other and alongside the one that does."""
import collections
import threading
import time
import unittest

from devteam.work_item import parse

from tests.journey import then
from tests.test_implement_journey import Played, analysed, blocked, sound
from tests.test_request_journey import QUESTIONS


class Concurrency(Played):
    def setUp(self):
        super().setUp()
        self.started = collections.defaultdict(threading.Event)
        self.running = set()
        self.overlaps = []

    def meet(self, mine, theirs):
        """Announce this step has started, then wait until the other has too; failing that, submit nothing."""
        def turn(agent):
            self.started[mine].set()
            if not self.started[theirs].wait(10):
                return 3
        return turn

    def alone(self, mine):
        def turn(agent):
            if self.running:
                self.overlaps.append(mine)
            self.running.add(mine)
            time.sleep(0.2)
            self.running.discard(mine)
        return turn

    def capture(self, title):
        item = self.team.create("story", title, "overview: As a cook, I want to plan.\n")
        self.team.record(item.id, "analyse")
        return item.id

    def committed(self, item_id):
        return parse(self.git("show", f"devteam-backlog:stories/{item_id}.yaml"))

    def test_a_request_is_analysed_while_another_items_implementer_holds_the_checkout(self):
        self.agent.plan_by_title({
            "breakfast": [analysed, sound, then(self.meet("implementing", "analysing"), blocked)],
            "pantry": [then(self.meet("analysing", "implementing"), QUESTIONS)]})
        self.capture("Plan breakfast")
        self.run_once()
        self.team.record("STORY-001", "play")
        self.team.create("request", "Stock the pantry", "overview: I want a stocked pantry.\n")
        self.team.record("REQUEST-001", "analyse")

        self.run_once()

        self.assertEqual(("implement", "blocked", "ready"), self.history("STORY-001")[-1])
        self.assertEqual("answering", self.request().step)

    def test_two_items_are_analysed_at_once_and_both_are_recorded(self):
        self.agent.plan_by_title({"breakfast": [then(self.meet("breakfast", "supper"), analysed), sound],
                                  "supper": [then(self.meet("supper", "breakfast"), analysed), sound]})
        self.capture("Plan breakfast")
        self.capture("Plan supper")

        self.run_once()

        for item_id in ("STORY-001", "STORY-002"):
            with self.subTest(item_id=item_id):
                self.assertEqual([("captured", "analyse", "analysis"), ("analysis", "analysed", "challenge"),
                                  ("challenge", "sound", "ready")], self.history(item_id))
                self.assertEqual(self.story(item_id).model_dump(), self.committed(item_id).model_dump())
        self.assertEqual("", self.git("status", "--porcelain", cwd=self.product / "backlog"))

    def test_steps_that_hold_the_checkout_never_overlap(self):
        self.agent.plan_by_title({"breakfast": [analysed, sound, then(self.alone("breakfast"), blocked)],
                                  "supper": [analysed, sound, then(self.alone("supper"), blocked)]})
        self.capture("Plan breakfast")
        self.capture("Plan supper")
        self.run_once()
        self.team.record("STORY-001", "play")
        self.team.record("STORY-002", "play")

        self.run_once()

        self.assertEqual([], self.overlaps, "two checkout steps ran at once")
        for item_id in ("STORY-001", "STORY-002"):
            with self.subTest(item_id=item_id):
                self.assertEqual(("implement", "blocked", "ready"), self.history(item_id)[-1])


if __name__ == "__main__":
    unittest.main()
