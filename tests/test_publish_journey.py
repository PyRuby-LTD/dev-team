"""The default workflow's fifth group: publish a pull request, wait on it, then finish when merged or rework when rejected."""
import json
import os
import shutil
import unittest
from unittest.mock import patch

from tests.journey import ROOT, submit
from tests.test_implement_journey import blocked, implemented
from tests.test_review_journey import APPROVE
from tests.test_verify_journey import WRITTEN, Synced

PUBLISHED = submit("published", "pull_request: 7\nsummary: Plans a week of meals.\napi_changes: No API changes\n")


class PublishAndPullRequest(Synced):
    def setUp(self):
        super().setUp()
        tools = self.base / "bin"
        tools.mkdir()
        shutil.copy(ROOT / "tests" / "stubs" / "gh", tools / "gh")
        self.enterContext(patch.dict(os.environ, {"PATH": f"{tools}{os.pathsep}{os.environ['PATH']}",
                                                  "GH_STUB_ARGV": str(self.gh_calls),
                                                  "GH_STUB_FIXTURES": str(self.fixtures)}))
        shutil.copytree(ROOT / "tests" / "fixtures" / "gh", self.fixtures)
        self.pull_request("OPEN")

    @property
    def fixtures(self):
        return self.base / "gh"

    @property
    def gh_calls(self):
        return self.base / "gh-calls.jsonl"

    def pull_request(self, state):
        (self.fixtures / "state.json").write_text(json.dumps({"state": state}))

    def gh(self):
        return [json.loads(line) for line in self.gh_calls.read_text().splitlines()]

    def published(self, *then):
        self.play(implemented("planner.txt"), WRITTEN, APPROVE, PUBLISHED, *then)
        self.run_once()
        self.team.record("STORY-001", "pr")
        self.run_once()

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

        self.run_once()
        self.assertEqual("pull-request", self.story("STORY-001").step)

        self.git("fetch", "-q", "origin", cwd=self.writer)
        self.git("merge", "-q", "--no-ff", "-m", "Merge pull request #7", "origin/devteam/STORY-001", cwd=self.writer)
        self.git("push", "-q", "origin", "main", cwd=self.writer)
        merge = self.git("rev-parse", "HEAD", cwd=self.writer)
        self.pull_request("MERGED")

        self.run_once()

        self.assertEqual("done", self.story("STORY-001").step)
        self.assertEqual([("pull-request", "merged", "merged"), ("merged", "completed", "done")],
                         self.history("STORY-001")[-2:])
        self.assertEqual(merge, self.git("rev-parse", "main"))
        self.assertEqual("main", self.git("branch", "--show-current").strip())
        self.assertIn("planner.txt", self.files("main"))
        self.assertEqual("", self.git("status", "--porcelain"))

    def test_a_rejected_pull_request_puts_its_comments_before_the_implementer(self):
        self.published(blocked)

        self.refused(self.team.record, "STORY-001", "merged")
        self.assertEqual("pull-request", self.story("STORY-001").step)
        self.team.record("STORY-001", "rejected")
        self.run_once()

        self.assertEqual([("publish", "published", "pull-request"), ("pull-request", "rejected", "rejected"),
                          ("rejected", "completed", "implement"), ("implement", "blocked", "ready")],
                         self.history("STORY-001")[-4:])
        [rejection] = [entry for entry in self.seen_at("implement").pending("implement") if entry.step == "rejected"]
        self.assertEqual(7, rejection.output["pull_request"])
        self.assertEqual([("review", "alice", "Please rename the flag."),
                          ("inline", "bob", "Use the rejected harness here."),
                          ("conversation", "carol", "Please address the review before merging.")],
                         [(comment["kind"], comment["author"], comment["body"])
                          for comment in rejection.output["comments"]])
        self.assertEqual("workflows/default.json line 16", rejection.output["comments"][1]["location"])

    def test_the_publish_prompts_are_previewable(self):
        self.script(*self.ready("STORY-001"))
        self.run_once()
        for step in ("publish", "resolve-publish"):
            with self.subTest(step=step):
                self.previewable(step, "STORY-001")


if __name__ == "__main__":
    unittest.main()
