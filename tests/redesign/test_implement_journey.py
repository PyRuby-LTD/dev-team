"""The default workflow's second group, implement and test, each item on its own branch with a queue for the checkout."""
import unittest

from devteam.redesign.work_item import parse

from .test_default_journey import SOUND
from .test_request_journey import Product


def analysed(item_id):
    return f"""$DEV_TEAM backlog submit {item_id} analysed <<'OUTPUT'
acceptance_criteria:
  - A week of meals can be planned
OUTPUT
"""


def sound(item_id):
    return SOUND.replace("STORY-001", item_id)


def implemented(item_id, change):
    return f"""git branch --show-current
echo changed > {change}
$DEV_TEAM backlog submit {item_id} implemented <<'OUTPUT'
branch: devteam/{item_id}
libraries_added:
  - name: left-pad
    licence: MIT
tech_tasks: [Extract the planner]
surprises: [Weeks start on Sunday in the seed data]
opinions: [The planner wants a service]
OUTPUT
"""


def defect(item_id):
    return f"""git branch --show-current
git branch --list 'devteam/*'
echo journey > journey_test.txt
$DEV_TEAM backlog submit {item_id} defect <<'OUTPUT'
journeys:
  - journey: Plan a week
    action: new
defects: [Planning a week shows no meals]
OUTPUT
"""


def blocked(item_id, keep=None):
    copy = (f"python3 -c 'import os, shutil; shutil.copy(\"backlog/stories/{item_id}.yaml\", "
            f"os.environ[\"STUB_PROMPTS\"] + \"/{keep}\")'\n" if keep else "")
    return f"""git branch --show-current
{copy}$DEV_TEAM backlog submit {item_id} blocked <<'OUTPUT'
blocked_by: The meals need a supplier only the customer can choose
OUTPUT
"""


class Played(Product):
    def ready(self, *item_ids):
        plan = [{"sh": analysed(item_id)} for item_id in item_ids] + [{"sh": sound(item_id)} for item_id in item_ids]
        for item_id in item_ids:
            self.ok("backlog", "create", "story", f"Plan {item_id}", stdin="overview: As a cook, I want to plan.\n")
            self.ok("backlog", "record", item_id, "analyse")
        return plan

    def story(self, item_id):
        return self.item("stories", item_id)

    def history(self, item_id):
        return [(entry.step, entry.outcome, entry.to) for entry in self.story(item_id).step_outputs]

    def out(self, number, engine):
        return (self.prompts / f"{number:02d}-{engine}.out").read_text().split()

    def files(self, ref):
        return self.git("ls-tree", "-r", "--name-only", ref).split()


class ImplementAndTest(Played):
    def test_two_played_items_queue_for_the_checkout_and_each_works_on_its_own_branch(self):
        plan = self.ready("STORY-001", "STORY-002")
        self.script(*plan, {"sh": implemented("STORY-001", "planner.txt")}, {"sh": defect("STORY-001")},
                    {"sh": blocked("STORY-001")}, {"sh": implemented("STORY-002", "printer.txt")}, {"sh": defect("STORY-002")},
                    {"sh": blocked("STORY-002")})
        self.ok("run", "--once")
        self.ok("backlog", "record", "STORY-001", "play", stdin="feedback: Start with breakfast.\n")
        self.ok("backlog", "record", "STORY-002", "play")

        self.ok("run", "--once")

        self.assertEqual("devteam/STORY-001", self.out(5, "codex")[0])
        self.assertEqual("devteam/STORY-001", self.out(6, "claude")[0])
        self.assertNotIn("devteam/STORY-002", self.out(6, "claude"),
                         "STORY-002 started while STORY-001 held the checkout")
        self.assertEqual("devteam/STORY-001", self.out(7, "codex")[0])
        self.assertEqual("devteam/STORY-002", self.out(8, "codex")[0])
        self.assertEqual("devteam/STORY-002", self.out(9, "claude")[0])

        first, second = self.files("devteam/STORY-001"), self.files("devteam/STORY-002")
        self.assertIn("planner.txt", first)
        self.assertIn("journey_test.txt", first)
        self.assertNotIn("printer.txt", first)
        self.assertIn("printer.txt", second)
        self.assertNotIn("planner.txt", second)
        self.assertEqual(self.git("rev-parse", "main"), self.git("merge-base", "devteam/STORY-001", "devteam/STORY-002"))

        for item_id in ("STORY-001", "STORY-002"):
            with self.subTest(item_id=item_id):
                self.assertEqual("ready", self.story(item_id).step)
                self.assertEqual([("ready", "play", "implement"), ("implement", "implemented", "test"),
                                  ("test", "defect", "implement"), ("implement", "blocked", "ready")],
                                 self.history(item_id)[-4:])
        implementation = self.story("STORY-001").step_outputs[-3].output
        self.assertEqual({"branch": "devteam/STORY-001",
                          "libraries_added": [{"name": "left-pad", "licence": "MIT"}],
                          "tech_tasks": ["Extract the planner"], "surprises": ["Weeks start on Sunday in the seed data"],
                          "opinions": ["The planner wants a service"]}, implementation)

    def test_a_tester_defect_returns_the_item_to_implement_with_the_defects_pending(self):
        plan = self.ready("STORY-001")
        self.script(*plan, {"sh": implemented("STORY-001", "planner.txt")}, {"sh": defect("STORY-001")},
                    {"sh": blocked("STORY-001", keep="item-seen-after-defect.yaml")})
        self.ok("run", "--once")
        self.ok("backlog", "record", "STORY-001", "play")

        self.ok("run", "--once")

        seen = parse((self.prompts / "item-seen-after-defect.yaml").read_text())
        self.assertEqual("implement", seen.step)
        self.assertEqual([("test", "defect", ["Planning a week shows no meals"])],
                         [(entry.step, entry.outcome, entry.output["defects"]) for entry in seen.pending("implement")])

    def test_the_backlog_stays_on_its_own_branch_apart_from_product_code(self):
        plan = self.ready("STORY-001")
        self.script(*plan, {"sh": implemented("STORY-001", "planner.txt")}, {"sh": defect("STORY-001")},
                    {"sh": blocked("STORY-001")})
        self.ok("run", "--once")
        self.ok("backlog", "record", "STORY-001", "play")

        self.ok("run", "--once")

        product = self.files("devteam/STORY-001")
        self.assertIn("planner.txt", product)
        self.assertEqual([], [name for name in product if name.startswith("backlog/") or name.endswith(".yaml")])
        backlog = self.files("devteam-backlog")
        self.assertIn("stories/STORY-001.yaml", backlog)
        self.assertNotIn("planner.txt", backlog)
        self.assertEqual("", self.git("status", "--porcelain"))

    def test_implement_and_test_prompts_are_previewable(self):
        self.script(*self.ready("STORY-001"))
        self.ok("run", "--once")
        for step in ("implement", "test"):
            with self.subTest(step=step):
                self.assertTrue(self.ok("prompt", step, "--item", "STORY-001").stdout.strip())


if __name__ == "__main__":
    unittest.main()
