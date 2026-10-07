"""STORY-013: re-publishing after a rejection, through the real runner, roles.toml and the claude stub."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from devteam import engines, git
from devteam.backlog import Repository
from devteam.config import ROOT, load_roles
from devteam.runner import Runner

IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
PUBLISHED = '{"type":"result","subtype":"success","result":"Done.\\nTRANSITION: published"}\n'
FIRST_PR = "https://github.com/example/product/pull/7"
HAPPY_PATH = ["analyse", "analysed", "sound", "play", "implemented", "written", "passed", "approve", "pr"]


class RepublishAfterRejection(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        bin_dir = base / "bin"
        bin_dir.mkdir()
        shim = bin_dir / "claude"
        shim.write_text("#!/bin/sh\nexec %s %s \"$@\"\n" % (sys.executable, ROOT / "tests" / "stubs" / "claude"))
        shim.chmod(0o755)
        env = dict(IDENTITY, PATH=str(bin_dir) + os.pathsep + os.environ["PATH"],
                   STUB_ARGV=str(base / "argv.json"), STUB_STDOUT=str(base / "stdout.jsonl"))
        (base / "stdout.jsonl").write_text(PUBLISHED)
        patcher = patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.argv = base / "argv.json"
        self.remote = base / "remote.git"
        self.product = base / "product"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.remote)], check=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.product)], check=True)
        (self.product / "app.txt").write_text("v1\n")
        git.commit_all(self.product, "init")
        git.must(self.product, "remote", "add", "origin", str(self.remote))
        git.must(self.product, "push", "-q", "origin", "main")
        self.roles = load_roles()
        self.repo = Repository(git.ensure_backlog(self.product), ROOT / "workflows", self.roles)
        epic = self.repo.create("epic", "Epic")
        self.story = self.repo.create("story", "Re-publish", "Body\n\n## Pull request\n\n" + FIRST_PR + "\n",
                                      parent=epic.id)
        self.messages = []
        self.runner = Runner(self.repo, self.roles, engines.run, self.messages.append, checkout=self.product)

    def step(self):
        return self.repo.scan().valid[self.story.id].metadata["step"]

    def publish(self, path):
        """Walk the item to publish by hand, then let the runner run the publisher for real."""
        for name in path:
            self.repo.transition(self.story.id, name)
        self.argv.unlink(missing_ok=True)
        self.runner.run(once=True)
        self.assertEqual("pull-request", self.step(), self.messages)
        return json.loads(self.argv.read_text())

    def remote_branch_log(self):
        return git.must(self.remote, "log", "--format=%s", "devteam/" + self.story.id)

    def republish(self):
        self.publish(HAPPY_PATH)
        self.repo.transition(self.story.id, "rejected")
        self.repo.transition(self.story.id, "completed")
        (self.product / "rework.txt").write_text("after review\n")
        git.commit_all(self.product, "rework after rejection")
        return self.publish(["implemented", "written", "passed", "approve", "pr"])

    def test_second_publish_pushes_new_commits_before_the_publisher_runs(self):
        self.publish(HAPPY_PATH)
        self.assertNotIn("rework after rejection", self.remote_branch_log())
        self.repo.transition(self.story.id, "rejected")
        self.repo.transition(self.story.id, "completed")
        (self.product / "rework.txt").write_text("after review\n")
        git.commit_all(self.product, "rework after rejection")
        self.publish(["implemented", "written", "passed", "approve", "pr"])
        self.assertIn("rework after rejection", self.remote_branch_log())

    def test_second_publish_prompt_looks_up_the_open_pr_before_creating_one(self):
        argv = self.republish()
        prompt = argv[argv.index("-p") + 1]
        self.assertIn("gh pr list --head devteam/%s --state open --json url" % self.story.id, prompt)
        self.assertIn("If an open PR exists, do not run `gh pr create`", " ".join(prompt.split()))
        self.assertIn("gh pr edit", prompt)
        self.assertLess(prompt.index("gh pr list"), prompt.index("gh pr create"))
        self.assertIn("Do not run `git push` or `git commit` yourself", " ".join(prompt.split()))

    def test_publisher_is_launched_with_the_gh_calls_it_needs_and_not_merge(self):
        argv = self.republish()
        allowed = argv[argv.index("--allowedTools") + 1]
        for call in ("gh pr list *", "gh pr edit *", "gh pr create *"):
            self.assertIn("Bash(%s)" % call, allowed)
        self.assertNotIn("gh pr merge", allowed)

    def test_publisher_brief_covers_an_existing_pr(self):
        argv = self.republish()
        brief = argv[argv.index("--append-system-prompt") + 1]
        prose = " ".join(brief.split())
        self.assertIn("Update the existing open pull request", prose)
        self.assertIn("when no open PR exists", prose)

    def test_item_keeps_its_single_pr_url_through_the_rejection_loop(self):
        self.republish()
        body = self.repo.scan().valid[self.story.id].body
        self.assertEqual(1, body.count("## Pull request"))
        self.assertEqual(1, body.count(FIRST_PR))


if __name__ == "__main__":
    unittest.main()
