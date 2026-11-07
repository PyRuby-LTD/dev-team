"""The default workflow's fifth group: publish a pull request, wait on it, then finish when merged or rework when rejected."""
import json
import shutil
import unittest

from devteam.redesign.work_item import parse

from .test_implement_journey import blocked, implemented
from .test_request_journey import ROOT
from .test_review_journey import APPROVE
from .test_verify_journey import WRITTEN, Synced

PUBLISHED = """gh pr list --head devteam/STORY-001 --state open --json number
gh pr create --head devteam/STORY-001 --base main --title "Plan STORY-001" --body-file - <<'EOF'
STORY-001: Plan STORY-001. Plans a week of meals.
EOF
$DEV_TEAM backlog submit STORY-001 published <<'OUTPUT'
pull_request: 7
summary: Plans a week of meals.
api_changes: No API changes
OUTPUT
"""


class PublishAndPullRequest(Synced):
    def setUp(self):
        super().setUp()
        shutil.copy(ROOT / "tests" / "stubs" / "gh", self.bin / "gh")
        shutil.copytree(ROOT / "tests" / "fixtures" / "gh", self.fixtures)
        (self.fixtures / "list.json").write_text("[]\n")
        (self.fixtures / "create.json").write_text("https://github.com/o/meals/pull/7\n")
        self.pull_request("OPEN")

    @property
    def fixtures(self):
        return self.base / "gh"

    @property
    def gh_calls(self):
        return self.base / "gh-calls.jsonl"

    def dev_team(self, *args, env=None, **kwargs):
        return super().dev_team(*args, env={"GH_STUB_ARGV": str(self.gh_calls),
                                            "GH_STUB_FIXTURES": str(self.fixtures), **(env or {})}, **kwargs)

    def pull_request(self, state):
        (self.fixtures / "state.json").write_text(json.dumps({"state": state}))

    def gh(self):
        return [json.loads(line) for line in self.gh_calls.read_text().splitlines()]

    def published(self, *then):
        self.play(implemented("STORY-001", "planner.txt"), WRITTEN, APPROVE, PUBLISHED, *then)
        self.ok("run", "--once")
        self.ok("backlog", "record", "STORY-001", "pr")
        self.ok("run", "--once")

    def test_a_published_pull_request_waits_while_open_then_a_merge_updates_the_base_and_finishes(self):
        self.published()

        self.assertEqual("pull-request", self.story("STORY-001").step)
        self.assertEqual([("accept", "pr", "sync-publish"), ("sync-publish", "completed", "verify-publish"),
                          ("verify-publish", "passed", "publish"), ("publish", "published", "pull-request")],
                         self.history("STORY-001")[-4:])
        self.assertEqual({"pull_request": 7, "summary": "Plans a week of meals.", "api_changes": "No API changes"},
                         self.story("STORY-001").step_outputs[-1].output)
        self.assertEqual(self.git("rev-parse", "devteam/STORY-001"),
                         self.git("rev-parse", "devteam/STORY-001", cwd=self.base / "origin.git"))
        self.assertIn(["pr", "view", "7", "--json", "state"], self.gh())

        self.ok("run", "--once")
        self.assertEqual("pull-request", self.story("STORY-001").step)

        self.git("fetch", "-q", "origin", cwd=self.writer)
        self.git("merge", "-q", "--no-ff", "-m", "Merge pull request #7", "origin/devteam/STORY-001", cwd=self.writer)
        self.git("push", "-q", "origin", "main", cwd=self.writer)
        merge = self.git("rev-parse", "HEAD", cwd=self.writer)
        self.pull_request("MERGED")

        self.ok("run", "--once")

        self.assertEqual("done", self.story("STORY-001").step)
        self.assertEqual([("pull-request", "merged", "merged"), ("merged", "completed", "done")],
                         self.history("STORY-001")[-2:])
        self.assertEqual(merge, self.git("rev-parse", "main"))
        self.assertEqual("main", self.git("branch", "--show-current").strip())
        self.assertIn("planner.txt", self.files("main"))
        self.assertEqual("", self.git("status", "--porcelain"))

    def test_a_rejected_pull_request_puts_its_comments_before_the_implementer(self):
        self.published(blocked("STORY-001", keep="item-seen-after-rejection.yaml"))

        refused = self.dev_team("backlog", "record", "STORY-001", "merged")
        self.assertNotEqual(0, refused.returncode)
        self.assertEqual("pull-request", self.story("STORY-001").step)
        self.ok("backlog", "record", "STORY-001", "rejected")
        self.ok("run", "--once")

        self.assertEqual([("publish", "published", "pull-request"), ("pull-request", "rejected", "rejected"),
                          ("rejected", "completed", "implement"), ("implement", "blocked", "ready")],
                         self.history("STORY-001")[-4:])
        seen = parse((self.prompts / "item-seen-after-rejection.yaml").read_text())
        [rejection] = [entry for entry in seen.pending("implement") if entry.step == "rejected"]
        self.assertEqual(7, rejection.output["pull_request"])
        self.assertEqual([("review", "alice", "Please rename the flag."),
                          ("inline", "bob", "Use the rejected harness here."),
                          ("conversation", "carol", "Please address the review before merging.")],
                         [(comment["kind"], comment["author"], comment["body"])
                          for comment in rejection.output["comments"]])
        self.assertEqual("workflows/default.json line 16", rejection.output["comments"][1]["location"])

    def test_the_publish_prompts_are_previewable(self):
        self.script(*self.ready("STORY-001"))
        self.ok("run", "--once")
        for step in ("publish", "resolve-publish"):
            with self.subTest(step=step):
                self.assertTrue(self.ok("prompt", step, "--item", "STORY-001").stdout.strip())


if __name__ == "__main__":
    unittest.main()
