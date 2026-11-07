"""STORY-010: a published item waits at `pull-request` for the customer, driven through the devteam command line."""
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STUBS = ROOT / "tests" / "stubs"
STREAMS = ROOT / "tests" / "fixtures" / "streams"
DEFAULT = ROOT / "workflows" / "default.json"
TO_ACCEPT = ("analyse", "analysed", "sound", "play", "implemented", "written", "completed", "passed", "approve")


class DefaultWorkflowShape(unittest.TestCase):
    def setUp(self):
        self.steps = json.loads(DEFAULT.read_text())["steps"]

    def test_done_is_reachable_from_publish_only_through_the_pull_request(self):
        self.assertEqual({"published": "pull-request"}, self.steps["publish"]["transitions"])
        seen, queue = set(), ["publish"]
        while queue:
            name = queue.pop()
            if name in seen or name == "pull-request":
                continue
            seen.add(name)
            queue.extend(self.steps[name]["transitions"].values())
        self.assertNotIn("pull-request", seen)
        self.assertNotIn("done", seen)

    def test_pull_request_is_the_customers_and_leads_to_the_harness_steps(self):
        self.assertEqual({"owner": "human", "transitions": {"merged": "merged", "rejected": "rejected", "abandon": "abandoning"}},
                         self.steps["pull-request"])

    def test_harness_steps_complete_to_done_and_implement(self):
        self.assertEqual({"owner": "harness:merged", "transitions": {"completed": "done"}}, self.steps["merged"])
        self.assertEqual({"owner": "harness:rejected", "transitions": {"completed": "implement"}}, self.steps["rejected"])

    def test_accept_keeps_its_three_transitions(self):
        self.assertEqual({"owner": "human", "transitions": {"pr": "sync-publish", "revise": "implement", "abandon": "abandoning"}},
                         self.steps["accept"])


if __name__ == "__main__":
    unittest.main()
