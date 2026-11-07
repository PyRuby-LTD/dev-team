"""Steps that do not hold the checkout run alongside each other and alongside the one that does."""
import json
import unittest

from devteam.redesign.work_item import parse

from .test_implement_journey import Played, analysed, blocked, sound
from .test_request_journey import QUESTIONS


def meet(mine, theirs):
    """Announce this step has started, then wait until the other has too; failing that, submit nothing."""
    return f"""set -e
python3 -c 'import os, pathlib, time
here = pathlib.Path(os.environ["STUB_PROMPTS"])
(here / "{mine}.started").touch()
deadline = time.monotonic() + 10
while not (here / "{theirs}.started").exists():
    if time.monotonic() > deadline:
        raise SystemExit("{theirs} never started")
    time.sleep(0.05)'
"""


def alone(mine):
    return f"""python3 -c 'import os, pathlib, time
here = pathlib.Path(os.environ["STUB_PROMPTS"])
(here / "{mine}.running").touch()
if [other for other in here.glob("*.running") if other.stem != "{mine}"]:
    (here / "overlap").write_text("{mine}")
time.sleep(0.5)
(here / "{mine}.running").unlink()'
"""


class Concurrency(Played):
    def plan_by_title(self, plan):
        self.plan.write_text(json.dumps(plan))

    def capture(self, title):
        item_id = self.ok("backlog", "create", "story", title, stdin="overview: As a cook, I want to plan.\n").stdout.split(":")[0]
        self.ok("backlog", "record", item_id, "analyse")
        return item_id

    def committed(self, item_id):
        return parse(self.git("show", f"devteam-backlog:stories/{item_id}.yaml"))

    def test_a_request_is_analysed_while_another_items_implementer_holds_the_checkout(self):
        self.plan_by_title({"breakfast": [{"sh": analysed("STORY-001")}, {"sh": sound("STORY-001")},
                                   {"sh": meet("implementing", "analysing") + blocked("STORY-001")}],
                     "pantry": [{"sh": meet("analysing", "implementing") + QUESTIONS}]})
        self.capture("Plan breakfast")
        self.ok("run", "--once")
        self.ok("backlog", "record", "STORY-001", "play")
        self.ok("backlog", "create", "request", "Stock the pantry", stdin="overview: I want a stocked pantry.\n")
        self.ok("backlog", "record", "REQUEST-001", "analyse")

        self.ok("run", "--once")

        self.assertEqual(("implement", "blocked", "ready"), self.history("STORY-001")[-1])
        self.assertEqual("answering", self.request().step)

    def test_two_items_are_analysed_at_once_and_both_are_recorded(self):
        self.plan_by_title({"breakfast": [{"sh": meet("breakfast", "supper") + analysed("STORY-001")}, {"sh": sound("STORY-001")}],
                     "supper": [{"sh": meet("supper", "breakfast") + analysed("STORY-002")}, {"sh": sound("STORY-002")}]})
        self.capture("Plan breakfast")
        self.capture("Plan supper")

        self.ok("run", "--once")

        for item_id in ("STORY-001", "STORY-002"):
            with self.subTest(item_id=item_id):
                self.assertEqual([("captured", "analyse", "analysis"), ("analysis", "analysed", "challenge"),
                                  ("challenge", "sound", "ready")], self.history(item_id))
                self.assertEqual(self.story(item_id).model_dump(), self.committed(item_id).model_dump())
        self.assertEqual("", self.git("status", "--porcelain", cwd=self.product / "backlog"))

    def test_steps_that_hold_the_checkout_never_overlap(self):
        self.plan_by_title({"breakfast": [{"sh": analysed("STORY-001")}, {"sh": sound("STORY-001")},
                                   {"sh": alone("breakfast") + blocked("STORY-001")}],
                     "supper": [{"sh": analysed("STORY-002")}, {"sh": sound("STORY-002")},
                                {"sh": alone("supper") + blocked("STORY-002")}]})
        self.capture("Plan breakfast")
        self.capture("Plan supper")
        self.ok("run", "--once")
        self.ok("backlog", "record", "STORY-001", "play")
        self.ok("backlog", "record", "STORY-002", "play")

        self.ok("run", "--once")

        self.assertFalse((self.prompts / "overlap").exists(), "two checkout steps ran at once")
        for item_id in ("STORY-001", "STORY-002"):
            with self.subTest(item_id=item_id):
                self.assertEqual(("implement", "blocked", "ready"), self.history(item_id)[-1])


if __name__ == "__main__":
    unittest.main()
