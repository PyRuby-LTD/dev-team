"""STORY-010: a published item waits at `pull-request` for the customer, driven through the devteam command line."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
STUBS = ROOT / "tests" / "stubs"
STREAMS = ROOT / "tests" / "fixtures" / "streams"
DEFAULT = ROOT / "workflows" / "default.json"
TO_ACCEPT = ("analyse", "analysed", "sound", "play", "implemented", "written", "passed", "approve")


class PullRequestDecision(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.product = self.directory / "product"
        self.product.mkdir()
        self.bin = self.directory / "bin"
        self.bin.mkdir()
        shutil.copy(STUBS / "claude", self.bin / "claude")
        (self.bin / "claude").chmod(0o755)
        self.argv = self.directory / "argv.json"
        self.devteam("backlog", "capture", "epic", "Epic", "--id", "EPIC-001")
        self.capture("STORY-001")

    def devteam(self, *args, env=None, check=True):
        return subprocess.run([sys.executable, "-m", "devteam", "--product", str(self.product), *args],
                              cwd=ROOT, env={**os.environ, **(env or {})}, capture_output=True, text=True,
                              timeout=60, check=check)

    def capture(self, item):
        self.devteam("backlog", "capture", "story", "Story", "--id", item, "--parent", "EPIC-001")

    def move(self, *transitions, item="STORY-001"):
        for transition in transitions:
            self.devteam("backlog", "move", item, transition)

    def listing(self, item="STORY-001"):
        output = self.devteam("backlog", "list").stdout
        return next(line.split() for line in output.splitlines() if line.startswith(item))

    def run_once(self):
        # The stub records its arguments only when it is started, so a missing file means no agent ran.
        env = {"PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}", "STUB_ARGV": str(self.argv),
               "STUB_STDOUT": str(STREAMS / "success.jsonl")}
        return self.devteam("run", "--once", env=env)

    def at_pull_request(self, item="STORY-001"):
        self.move(*TO_ACCEPT, "pr", "published", item=item)

    def test_published_item_waits_for_the_customer_instead_of_reaching_done(self):
        self.move(*TO_ACCEPT, "pr")
        self.assertEqual(["STORY-001", "publish", "agent:publisher"], self.listing()[:3])
        moved = self.devteam("backlog", "move", "STORY-001", "published").stdout
        self.assertIn("pull-request (human)", moved)
        self.assertEqual(["STORY-001", "pull-request", "human"], self.listing()[:3])

    def test_runner_leaves_an_item_at_the_pull_request_step_alone(self):
        self.at_pull_request()
        self.run_once()
        self.assertEqual("pull-request", self.listing()[1])
        self.assertFalse(self.argv.exists())

    def test_customer_can_only_move_a_pull_request_to_merged_or_rejected(self):
        self.at_pull_request()
        for name in ("published", "completed", "accept"):
            refused = self.devteam("backlog", "move", "STORY-001", name, check=False)
            self.assertNotEqual(0, refused.returncode, name)
        self.assertEqual("pull-request", self.listing()[1])

    def test_merged_decision_is_completed_by_the_harness_without_an_agent(self):
        self.at_pull_request()
        moved = self.devteam("backlog", "move", "STORY-001", "merged").stdout
        self.assertIn("merged (harness:merged)", moved)
        result = self.run_once()
        self.assertIn("merged (harness: merged): completed -> done", result.stdout)
        self.assertEqual("done", self.listing()[1])
        self.assertFalse(self.argv.exists())

    def test_rejected_decision_returns_the_item_to_implement_without_an_agent_at_rejected(self):
        self.at_pull_request()
        moved = self.devteam("backlog", "move", "STORY-001", "rejected", "-m", "Rename the flag").stdout
        self.assertIn("rejected (harness:rejected)", moved)
        result = self.run_once()
        self.assertIn("rejected (harness: rejected): completed -> implement", result.stdout)
        self.assertEqual("implement", self.listing()[1])
        self.assertFalse(self.argv.exists())
        body = next((self.product / "backlog").rglob("STORY-001.md")).read_text()
        self.assertIn("Rename the flag", body)

    def test_accept_still_finishes_directly_and_the_pr_path_still_leads_to_publish(self):
        self.capture("STORY-002")
        self.move(*TO_ACCEPT, "accept")
        self.move(*TO_ACCEPT, "pr", item="STORY-002")
        self.assertEqual("done", self.listing()[1])
        self.assertEqual("publish", self.listing("STORY-002")[1])

    def test_default_workflow_validates_through_the_backlog_command(self):
        result = self.devteam("backlog", "validate")
        self.assertNotIn("ERROR", result.stdout + result.stderr)
        self.assertEqual("captured", self.listing()[1])

    def test_repository_backlog_validates_with_the_new_workflow(self):
        result = subprocess.run([sys.executable, "-m", "devteam", "--product", str(ROOT), "backlog", "validate"],
                                cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotIn("ERROR", result.stdout + result.stderr)


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
        self.assertEqual({"owner": "human", "transitions": {"merged": "merged", "rejected": "rejected"}},
                         self.steps["pull-request"])

    def test_harness_steps_complete_to_done_and_implement(self):
        self.assertEqual({"owner": "harness:merged", "transitions": {"completed": "done"}}, self.steps["merged"])
        self.assertEqual({"owner": "harness:rejected", "transitions": {"completed": "implement"}}, self.steps["rejected"])

    def test_accept_keeps_its_three_transitions(self):
        self.assertEqual({"owner": "human", "transitions": {"pr": "publish", "accept": "done", "revise": "implement"}},
                         self.steps["accept"])


class PullRequestHoldsTheCheckout(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.product = self.directory / "product"
        self.bin = self.directory / "bin"
        self.bin.mkdir()
        shutil.copy(STUBS / "claude", self.bin / "claude")
        (self.bin / "claude").chmod(0o755)
        self.argv = self.directory / "argv.json"
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.product)], check=True)
        (self.product / "README.md").write_text("product\n")
        git = ["git", "-C", str(self.product), "-c", "user.name=t", "-c", "user.email=t@example.com"]
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "commit", "-q", "-m", "init"], check=True)
        self.devteam("backlog", "capture", "epic", "Epic", "--id", "EPIC-001")
        for item in ("STORY-001", "STORY-002"):
            self.devteam("backlog", "capture", "story", "Story", "--id", item, "--parent", "EPIC-001")
        for transition in TO_ACCEPT[:4]:
            self.devteam("backlog", "move", "STORY-002", transition)
        for transition in (*TO_ACCEPT, "pr", "published"):
            self.devteam("backlog", "move", "STORY-001", transition)
        # STORY-001 has the checkout, as it would after its implement step.
        subprocess.run(["git", "-C", str(self.product), "switch", "-q", "-c", "devteam/STORY-001"], check=True)

    def devteam(self, *args, env=None):
        return subprocess.run([sys.executable, "-m", "devteam", "--product", str(self.product), *args],
                              cwd=ROOT, env={**os.environ, **(env or {})}, capture_output=True, text=True,
                              timeout=60, check=True)

    def run_once(self):
        env = {"PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}", "STUB_ARGV": str(self.argv),
               "STUB_STDOUT": str(STREAMS / "success.jsonl")}
        return self.devteam("run", "--once", env=env)

    def test_item_awaiting_the_customers_pull_request_decision_blocks_other_code_changes(self):
        listing = self.devteam("backlog", "list").stdout
        self.assertRegex(listing, r"STORY-001\s+pull-request\s+human")
        result = self.run_once()
        self.assertIn("waiting for STORY-001, which holds the checkout at step pull-request", result.stdout)
        self.assertFalse(self.argv.exists())
        branch = subprocess.run(["git", "-C", str(self.product), "branch", "--show-current"],
                                capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual("devteam/STORY-001", branch)


if __name__ == "__main__":
    unittest.main()
