"""The default workflow's third group, sync, resolve and verify, on the item's branch against its base on origin."""
import shutil
import subprocess
import unittest

from devteam.redesign.work_item import parse

from .test_implement_journey import Played, blocked, implemented

WRITTEN = """$DEV_TEAM backlog submit STORY-001 written <<'OUTPUT'
journeys:
  - journey: Plan a week
    action: new
OUTPUT
"""

RESOLVED = """python3 -c 'import os, shutil; shutil.copy("backlog/stories/STORY-001.yaml", os.environ["STUB_PROMPTS"] + "/item-seen-by-resolve.yaml")'
printf 'A meal planner for the week.\\n' > README.md
$DEV_TEAM backlog submit STORY-001 resolved
"""

BLOCKED_RESOLVE = """echo half-done > README.md
echo scratch > notes.txt
$DEV_TEAM backlog submit STORY-001 blocked <<'OUTPUT'
blocked_by: The base renames the planner the story changes
OUTPUT
"""

DEFECT_FROM_CHECK = """python3 -c 'import os, shutil; shutil.copy("backlog/stories/STORY-001.yaml", os.environ["STUB_PROMPTS"] + "/item-seen-by-tester.yaml")'
$DEV_TEAM backlog submit STORY-001 defect <<'OUTPUT'
defects: [The meals check fails]
OUTPUT
"""

FAILING_CHECK = """printf 'regression:\\n\\t@echo the meals check found no meals; false\\n' > Makefile
$DEV_TEAM backlog submit STORY-001 implemented <<'OUTPUT'
branch: devteam/STORY-001
OUTPUT
"""


class Synced(Played):
    def setUp(self):
        super().setUp()
        for tool in ("make", "true", "false"):
            (self.bin / tool).symlink_to(shutil.which(tool))
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

    def play(self, *steps):
        self.script(*self.ready("STORY-001"), *({"sh": sh} for sh in steps))
        self.ok("run", "--once")
        self.ok("backlog", "record", "STORY-001", "play")

    def succeeds(self, *args):
        return subprocess.run(["git", *args], cwd=self.product, capture_output=True).returncode == 0

    def ancestor(self, commit, ref):
        return self.succeeds("merge-base", "--is-ancestor", commit, ref)

    def merging(self):
        return self.succeeds("rev-parse", "--verify", "--quiet", "MERGE_HEAD")


class SyncVerifyResolve(Synced):
    def test_a_clean_sync_and_a_passing_check_reach_review(self):
        self.play(implemented("STORY-001", "planner.txt"), WRITTEN)
        base = self.base_change("pantry.txt", "flour\n")

        self.dev_team("run", "--once")

        self.assertEqual("review", self.story("STORY-001").step)
        self.assertEqual([("test", "written", "sync"), ("sync", "completed", "verify"),
                          ("verify", "passed", "review")], self.history("STORY-001")[-3:])
        self.assertTrue(self.ancestor(base, "devteam/STORY-001"), "the branch did not take its base")
        self.assertIn("planner.txt", self.files("devteam/STORY-001"))
        self.assertTrue(any((self.product / "backlog" / "log" / "STORY-001").glob("verify-*.log")))

    def test_a_conflicting_sync_goes_to_the_implementer_who_resolves_it(self):
        self.play(implemented("STORY-001", "README.md"), WRITTEN, RESOLVED)
        base = self.base_change("README.md", "A meal planner for a household.\n")

        self.dev_team("run", "--once")

        self.assertEqual([("sync", "conflicted", "resolve"), ("resolve", "resolved", "verify"),
                          ("verify", "passed", "review")], self.history("STORY-001")[-3:])
        seen = parse((self.prompts / "item-seen-by-resolve.yaml").read_text())
        self.assertEqual([("sync", "conflicted", {"conflicts": ["README.md"]})],
                         [(entry.step, entry.outcome, entry.output) for entry in seen.pending("resolve")])
        self.assertTrue(self.ancestor(base, "devteam/STORY-001"), "the merge was not committed")
        self.assertFalse(self.merging())
        self.assertEqual("A meal planner for the week.\n", self.git("show", "devteam/STORY-001:README.md"))
        self.assertEqual("", self.git("status", "--porcelain"))

    def test_a_resolve_the_implementer_cannot_do_returns_to_ready_with_the_merge_aborted(self):
        self.play(implemented("STORY-001", "README.md"), WRITTEN, BLOCKED_RESOLVE)
        self.base_change("README.md", "A meal planner for a household.\n")

        self.ok("run", "--once")

        self.assertEqual("ready", self.story("STORY-001").step)
        self.assertEqual([("sync", "conflicted", "resolve"), ("resolve", "blocked", "ready")],
                         self.history("STORY-001")[-2:])
        self.assertEqual({"blocked_by": "The base renames the planner the story changes"},
                         self.story("STORY-001").step_outputs[-1].output)
        self.assertFalse(self.merging())
        self.assertEqual("", self.git("status", "--porcelain"))
        self.assertEqual("changed\n", (self.product / "README.md").read_text())

    def test_a_failing_check_sends_the_item_back_to_test_with_the_checks_summary(self):
        self.play(FAILING_CHECK, WRITTEN, DEFECT_FROM_CHECK, blocked("STORY-001"))

        self.ok("run", "--once")

        self.assertEqual([("test", "written", "sync"), ("sync", "completed", "verify"), ("verify", "failed", "test"),
                          ("test", "defect", "implement"), ("implement", "blocked", "ready")],
                         self.history("STORY-001")[-5:])
        seen = parse((self.prompts / "item-seen-by-tester.yaml").read_text())
        [check] = [entry for entry in seen.pending("test") if entry.step == "verify"]
        self.assertEqual("failed", check.outcome)
        self.assertIn("the meals check found no meals", check.output["summary"])

    def test_the_resolve_prompt_is_previewable(self):
        self.script(*self.ready("STORY-001"))
        self.ok("run", "--once")
        self.assertTrue(self.ok("prompt", "resolve", "--item", "STORY-001").stdout.strip())


if __name__ == "__main__":
    unittest.main()
