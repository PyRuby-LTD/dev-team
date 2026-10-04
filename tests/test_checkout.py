import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from devteam import git
from devteam.backlog import Repository
from devteam.cli import main
from devteam.config import Role
from devteam.runner import Runner

WORKFLOW = {
    "initial": "ready",
    "steps": {
        "ready": {"owner": "human", "transitions": {"play": "implement", "analyse": "analysis"}},
        "analysis": {"owner": "agent:analyst", "transitions": {"ready": "ready"}},
        "implement": {"owner": "agent:implementer", "transitions": {"implemented": "review"}},
        "review": {"owner": "agent:reviewer", "transitions": {"approve": "accept"}},
        "accept": {"owner": "human", "transitions": {"pr": "publish", "accept": "done"}},
        "publish": {"owner": "agent:publisher", "transitions": {"published": "done"}},
        "done": {"owner": "human", "transitions": {}},
    },
}
IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def role(name, branch=False, record=False):
    return Role(name, "fake", "m", 5, ["fake"], "w", branch, record)


class CheckoutAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patcher = patch.dict(os.environ, IDENTITY)
        patcher.start()
        self.addCleanup(patcher.stop)
        base = Path(self.temp.name).resolve()
        self.remote = base / "remote.git"
        self.product = base / "product"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.remote)], check=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.product)], check=True)
        (self.product / "app.txt").write_text("v1\n")
        git.commit_all(self.product, "init")
        git.must(self.product, "remote", "add", "origin", str(self.remote))
        git.must(self.product, "push", "-q", "origin", "main")
        workflows = base / "workflows"
        workflows.mkdir()
        (workflows / "default.json").write_text(json.dumps(WORKFLOW))
        self.roles = {"analyst": role("analyst"), "implementer": role("implementer", True),
                      "reviewer": role("reviewer", True), "publisher": role("publisher", True, True)}
        self.backlog = git.ensure_backlog(self.product)
        self.repo = Repository(self.backlog, workflows, self.roles)
        self.epic = self.repo.create("epic", "Epic")
        self.first = self.repo.create("story", "First", parent=self.epic.id)
        self.second = self.repo.create("story", "Second", parent=self.epic.id)
        self.messages = []
        self.calls = []
        self.runner = Runner(self.repo, self.roles, self.engine, self.messages.append, checkout=self.product)

    def engine(self, role, prompt, cwd, extra_dir, log):
        item = "STORY-001" if "STORY-001.md" in prompt else "STORY-002"
        self.calls.append((item, role.name, prompt, cwd, git.current_branch(self.product)))
        log.write_text("transcript")
        if role.name == "implementer":
            (cwd / f"{item}.txt").write_text("change\n")
            git.commit_all(cwd, f"{item}: change")
            return 0, "TRANSITION: implemented"
        if role.name == "publisher":
            git.must(cwd, "push", "-q", "-u", "origin", f"devteam/{item}")
            return 0, "TRANSITION: published"
        return 0, "TRANSITION: " + {"analyst": "ready", "reviewer": "approve"}[role.name]

    def steps(self):
        return {key: record.metadata.get("step") for key, record in self.repo.scan().valid.items()}

    def commits(self, directory, ref="HEAD"):
        return git.must(directory, "log", "--format=%s", ref).splitlines()

    def test_backlog_branch_is_separate_and_hidden_from_the_code_branch(self):
        self.assertEqual("devteam-backlog", git.current_branch(self.backlog))
        self.assertNotEqual(0, git.run(self.product, "merge-base", "main", "devteam-backlog").returncode)
        self.assertEqual("", git.must(self.product, "status", "--porcelain"))
        self.assertEqual(self.backlog, git.ensure_backlog(self.product))
        self.assertEqual(self.product, git.checkout(self.backlog))

    def test_backlog_attaches_to_a_remote_branch_in_a_fresh_clone(self):
        git.must(self.backlog, "push", "-q", "origin", "devteam-backlog")
        clone = Path(self.temp.name).resolve() / "clone"
        subprocess.run(["git", "clone", "-q", str(self.remote), str(clone)], check=True)
        backlog = git.ensure_backlog(clone)
        self.assertTrue((backlog / "stories" / "STORY-001.md").exists())
        self.assertEqual("", git.must(clone, "status", "--porcelain"))

    def test_capture_and_transitions_commit_to_the_backlog_branch(self):
        before = self.commits(self.backlog)
        self.assertEqual("STORY-002: captured at ready", before[0])
        self.repo.transition(self.first.id, "play")
        after = self.commits(self.backlog)
        self.assertEqual(["STORY-001: play -> implement"], after[:len(after) - len(before)])
        self.assertEqual("", git.must(self.backlog, "status", "--porcelain"))

    def test_cli_sets_up_the_backlog_in_a_new_product(self):
        product = Path(self.temp.name).resolve() / "fresh"
        subprocess.run(["git", "init", "-q", "-b", "main", str(product)], check=True)
        with patch("builtins.print"):
            main(["--product", str(product), "backlog", "capture", "epic", "Fresh"])
        self.assertTrue((product / "backlog" / "epics" / "EPIC-001.md").exists())
        self.assertEqual(["EPIC-001: captured", "Start the backlog"], self.commits(product / "backlog"))
        self.assertEqual("", git.must(product, "status", "--porcelain"))

    def test_implementer_and_reviewer_work_in_the_checkout_on_the_item_branch(self):
        self.repo.transition(self.first.id, "play")
        self.runner.run(once=True)
        self.assertEqual("accept", self.steps()["STORY-001"])
        self.assertEqual([("implementer", "devteam/STORY-001"), ("reviewer", "devteam/STORY-001")],
                         [(call[1], call[4]) for call in self.calls])
        self.assertEqual({self.product}, {call[3] for call in self.calls})
        self.assertEqual("main", git.base_of(self.product, "devteam/STORY-001"))
        self.assertIn("git diff main...devteam/STORY-001", self.calls[1][2])
        self.assertTrue((self.product / "STORY-001.txt").exists())

    def test_one_item_holds_the_checkout_and_analysis_still_runs(self):
        self.repo.transition(self.first.id, "play")
        self.runner.run(once=True)
        self.repo.transition(self.second.id, "play")
        third = self.repo.create("story", "Third", parent=self.epic.id)
        self.repo.transition(third.id, "analyse")
        self.calls.clear()
        self.runner.run(once=True)
        self.runner.run(once=True)
        self.assertEqual(["analyst"], [call[1] for call in self.calls])
        self.assertEqual("implement", self.steps()["STORY-002"])
        waiting = [m for m in self.messages if "waiting for STORY-001" in m]
        self.assertEqual(1, len(waiting))
        self.assertEqual("devteam/STORY-001", git.current_branch(self.product))

    def test_next_item_branches_from_the_base_once_the_holder_is_terminal(self):
        self.repo.transition(self.first.id, "play")
        self.repo.transition(self.second.id, "play")
        self.runner.run(once=True)
        self.repo.transition(self.first.id, "accept")
        before = self.steps()
        self.runner.run(once=True)
        self.assertEqual("devteam/STORY-002", git.current_branch(self.product))
        self.assertEqual("main", git.base_of(self.product, "devteam/STORY-002"))
        self.assertEqual(["STORY-002: change", "init"], self.commits(self.product))
        self.assertFalse((self.product / "STORY-001.txt").exists())
        self.assertEqual({**before, "STORY-002": "accept"}, self.steps())

    def test_uncommitted_changes_prevent_a_switch(self):
        self.repo.transition(self.first.id, "play")
        (self.product / "app.txt").write_text("my edit\n")
        self.runner.run(once=True)
        self.assertEqual([], self.calls)
        self.assertEqual("main", git.current_branch(self.product))
        self.assertEqual("implement", self.steps()["STORY-001"])
        self.assertIn("uncommitted changes", self.messages[-1])
        git.must(self.product, "checkout", "--", "app.txt")
        self.runner.run(once=True)
        self.assertEqual("accept", self.steps()["STORY-001"])

    def test_pr_transition_publishes_with_a_record_of_the_item(self):
        self.repo.transition(self.first.id, "play")
        self.runner.run(once=True)
        self.repo.transition(self.first.id, "pr")
        self.runner.run(once=True)
        self.assertEqual("done", self.steps()["STORY-001"])
        self.assertEqual("publisher", self.calls[-1][1])
        self.assertIn("base branch is main", self.calls[-1][2])
        record = git.must(self.remote, "show", "devteam/STORY-001:docs/work-items/STORY-001.md")
        self.assertIn("id: STORY-001", record)
        self.assertIn("title: First", record)
        self.assertEqual(["STORY-001: record the work item", "STORY-001: change", "init"],
                         self.commits(self.remote, "devteam/STORY-001"))
        self.assertNotEqual(0, git.run(self.remote, "cat-file", "-e", "main:docs/work-items/STORY-001.md").returncode)


if __name__ == "__main__":
    unittest.main()
