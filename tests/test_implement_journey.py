"""The default workflow's second group: each played item is implemented and tested on its own branch, one at a time."""
import unittest

from tests.journey import Product, submit


analysed = submit("analysed", "acceptance_criteria:\n  - A week of meals can be planned\n")
sound = submit("sound", "findings: []\n")


def implemented(change):
    def turn(agent):
        agent.write(change, "changed\n")
        agent.submit("implemented", f"""branch: devteam/{agent.item_id}
libraries_added:
  - name: left-pad
    licence: MIT
tech_tasks: [Extract the planner]
surprises: [Weeks start on Sunday in the seed data]
opinions: [The planner wants a service]
""")
    return turn


def defect(agent):
    agent.write("journey_test.txt", "journey\n")
    agent.submit("defect", "journeys:\n  - journey: Plan a week\n    action: new\ndefects: [Planning a week shows no meals]\n")


blocked = submit("blocked", "blocked_by: The meals need a supplier only the customer can choose\n")


class Played(Product):
    def ready(self, item_id):
        """Capture a story for analysis; the agent turns that take it to ready."""
        self.team.create("story", f"Plan {item_id}", "overview: As a cook, I want to plan.\n")
        self.team.record(item_id, "analyse")
        return [analysed, sound]

    def story(self, item_id):
        return self.item("stories", item_id)

    def history(self, item_id):
        return [(entry.step, entry.outcome, entry.to) for entry in self.story(item_id).step_outputs]

    def files(self, ref):
        return self.git("ls-tree", "-r", "--name-only", ref).split()


class ImplementAndTest(Played):
    def test_two_played_items_queue_for_the_checkout_and_each_works_on_its_own_branch(self):
        # Analysed one after the other: run in parallel, either item's agent could take the other's turn.
        self.script(*self.ready("STORY-001"), analysed, sound, implemented("planner.txt"), defect, blocked,
                    implemented("printer.txt"), defect, blocked)
        self.run_once()
        self.ready("STORY-002")
        self.run_once()
        self.team.record("STORY-001", "play", "feedback: Start with breakfast.\n")
        self.team.record("STORY-002", "play")

        self.run_once()

        self.assertEqual([("STORY-001", "devteam/STORY-001", "codex"), ("STORY-001", "devteam/STORY-001", "claude"),
                          ("STORY-001", "devteam/STORY-001", "codex"), ("STORY-002", "devteam/STORY-002", "codex"),
                          ("STORY-002", "devteam/STORY-002", "claude"), ("STORY-002", "devteam/STORY-002", "codex")],
                         [(agent.item_id, agent.branch, agent.engine) for agent in self.agent.agents[4:]],
                         "STORY-002 started while STORY-001 held the checkout")

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
        self.script(*self.ready("STORY-001"), implemented("planner.txt"), defect, blocked)
        self.run_once()
        self.team.record("STORY-001", "play")

        self.run_once()

        seen = self.seen(5).item
        self.assertEqual("implement", seen.step)
        self.assertEqual([("test", "defect", ["Planning a week shows no meals"])],
                         [(entry.step, entry.outcome, entry.output["defects"]) for entry in seen.pending("implement")])

    def test_the_backlog_stays_on_its_own_branch_apart_from_product_code(self):
        self.script(*self.ready("STORY-001"), implemented("planner.txt"), defect, blocked)
        self.run_once()
        self.team.record("STORY-001", "play")

        self.run_once()

        product = self.files("devteam/STORY-001")
        self.assertIn("planner.txt", product)
        self.assertEqual([], [name for name in product if name.startswith("backlog/") or name.endswith(".yaml")])
        backlog = self.files("devteam-backlog")
        self.assertIn("stories/STORY-001.yaml", backlog)
        self.assertNotIn("planner.txt", backlog)
        self.assertEqual("", self.git("status", "--porcelain"))

    def test_implement_and_test_prompts_are_previewable(self):
        self.script(*self.ready("STORY-001"))
        self.run_once()
        for step in ("implement", "test"):
            with self.subTest(step=step):
                self.previewable(step, "STORY-001")


if __name__ == "__main__":
    unittest.main()
