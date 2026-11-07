"""The default workflow's third group, sync, resolve and verify, on the item's branch against its base on origin."""
import subprocess
import unittest

from .journey import submit
from .test_implement_journey import Played, blocked, implemented

WRITTEN = submit("written", "journeys:\n  - journey: Plan a week\n    action: new\n")


def resolved(agent):
    agent.write("README.md", "A meal planner for the week.\n")
    agent.submit("resolved")


def blocked_resolve(agent):
    agent.write("README.md", "half-done\n")
    agent.write("notes.txt", "scratch\n")
    agent.submit("blocked", "blocked_by: The base renames the planner the story changes\n")


DEFECT_FROM_CHECK = submit("defect", "defects: [The meals check fails]\n")


def failing_check(agent):
    agent.write("Makefile", "regression:\n\t@echo the meals check found no meals; false\n")
    agent.submit("implemented", "branch: devteam/STORY-001\n")


class Synced(Played):
    def setUp(self):
        super().setUp()
        origin = self.base / "origin.git"
        self.git("init", "-q", "--bare", "-b", "main", str(origin))
        self.git("remote", "set-url", "origin", str(origin))
        self.git("push", "-q", "origin", "main")
        self.writer = self.base / "writer"
        self.git("clone", "-q", str(origin), str(self.writer))

    def base_change(self, name, text):
        (self.writer / name).write_text(text)
        self.git("add", "-A", cwd=self.writer)
        self.git("commit", "-q", "-m", f"Change {name} on main", cwd=self.writer)
        self.git("push", "-q", "origin", "main", cwd=self.writer)
        return self.git("rev-parse", "HEAD", cwd=self.writer).strip()

    def play(self, *turns):
        self.script(*self.ready("STORY-001"), *turns)
        self.run_once()
        self.team.record("STORY-001", "play")

    def succeeds(self, *args):
        return subprocess.run(["git", *args], cwd=self.product, capture_output=True).returncode == 0

    def ancestor(self, commit, ref):
        return self.succeeds("merge-base", "--is-ancestor", commit, ref)

    def merging(self):
        return self.succeeds("rev-parse", "--verify", "--quiet", "MERGE_HEAD")


class SyncVerifyResolve(Synced):
    def test_a_clean_sync_and_a_passing_check_reach_review(self):
        self.play(implemented("planner.txt"), WRITTEN)
        base = self.base_change("pantry.txt", "flour\n")

        self.team.run(once=True)

        self.assertEqual("review", self.story("STORY-001").step)
        self.assertEqual([("test", "written", "sync"), ("sync", "completed", "verify"),
                          ("verify", "passed", "review")], self.history("STORY-001")[-3:])
        self.assertTrue(self.ancestor(base, "devteam/STORY-001"), "the branch did not take its base")
        self.assertIn("planner.txt", self.files("devteam/STORY-001"))
        self.assertTrue(any((self.product / "backlog" / "log" / "STORY-001").glob("verify-*.log")))

    def test_a_conflicting_sync_goes_to_the_implementer_who_resolves_it(self):
        self.play(implemented("README.md"), WRITTEN, resolved)
        base = self.base_change("README.md", "A meal planner for a household.\n")

        self.team.run(once=True)

        self.assertEqual([("sync", "conflicted", "resolve"), ("resolve", "resolved", "verify"),
                          ("verify", "passed", "review")], self.history("STORY-001")[-3:])
        self.assertEqual([("sync", "conflicted", {"conflicts": ["README.md"]})],
                         [(entry.step, entry.outcome, entry.output) for entry in self.seen_at("resolve").pending("resolve")])
        self.assertTrue(self.ancestor(base, "devteam/STORY-001"), "the merge was not committed")
        self.assertFalse(self.merging())
        self.assertEqual("A meal planner for the week.\n", self.git("show", "devteam/STORY-001:README.md"))
        self.assertEqual("", self.git("status", "--porcelain"))

    def test_a_resolve_the_implementer_cannot_do_returns_to_ready_with_the_merge_aborted(self):
        self.play(implemented("README.md"), WRITTEN, blocked_resolve)
        self.base_change("README.md", "A meal planner for a household.\n")

        self.run_once()

        self.assertEqual("ready", self.story("STORY-001").step)
        self.assertEqual([("sync", "conflicted", "resolve"), ("resolve", "blocked", "ready")],
                         self.history("STORY-001")[-2:])
        self.assertEqual({"blocked_by": "The base renames the planner the story changes"},
                         self.story("STORY-001").step_outputs[-1].output)
        self.assertFalse(self.merging())
        self.assertEqual("", self.git("status", "--porcelain"))
        self.assertEqual("changed\n", (self.product / "README.md").read_text())

    def test_a_failing_check_sends_the_item_back_to_test_with_the_checks_summary(self):
        self.play(failing_check, WRITTEN, DEFECT_FROM_CHECK, blocked)

        self.run_once()

        self.assertEqual([("test", "written", "sync"), ("sync", "completed", "verify"), ("verify", "failed", "test"),
                          ("test", "defect", "implement"), ("implement", "blocked", "ready")],
                         self.history("STORY-001")[-5:])
        [check] = [entry for entry in self.seen_at("test").pending("test") if entry.step == "verify"]
        self.assertEqual("failed", check.outcome)
        self.assertIn("the meals check found no meals", check.output["summary"])

    def test_the_resolve_prompt_is_previewable(self):
        self.script(*self.ready("STORY-001"))
        self.run_once()
        self.previewable("resolve", "STORY-001")


if __name__ == "__main__":
    unittest.main()
