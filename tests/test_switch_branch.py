import threading
import unittest

from devteam import git, tui
from devteam.runner import StepFailed, Waiting
from tests import test_checkout as fixtures


class SwitchBranch(unittest.TestCase):
    engine = fixtures.CheckoutAcceptance.engine

    def setUp(self):
        fixtures.CheckoutAcceptance.setUp(self)
        self.repo.transition(self.first.id, "play")
        self.runner.run(once=True)
        self.branch = f"devteam/{self.first.id}"
        self.tip = git.must(self.product, "rev-parse", "HEAD")
        git.must(self.product, "switch", "-q", "main")

    def test_switches_to_existing_branch_at_human_and_checkout_steps_without_changing_work(self):
        self.assertEqual(self.branch, self.runner.switch_branch(self.first.id))
        self.assertEqual(self.tip, git.must(self.product, "rev-parse", "HEAD"))
        self.assertEqual("accept", self.repo.scan().valid[self.first.id].metadata["step"])
        self.repo.transition(self.first.id, "revise")
        git.must(self.product, "switch", "-q", "main")
        self.runner.switch_branch(self.first.id)
        self.assertEqual(self.tip, git.must(self.product, "rev-parse", "HEAD"))
        self.runner.run(once=True)
        self.assertIn(self.tip, git.must(self.product, "rev-list", "HEAD").splitlines())

    def test_missing_branch_is_reported_without_creating_it(self):
        with self.assertRaisesRegex(StepFailed, "No existing branch"):
            self.runner.switch_branch(self.second.id)
        self.assertFalse(git.has_ref(self.product, f"refs/heads/devteam/{self.second.id}"))
        self.assertEqual("main", git.current_branch(self.product))

    def test_dirty_tracked_and_untracked_work_is_preserved(self):
        for name in ("app.txt", "local-output"):
            with self.subTest(name=name):
                path = self.product / name
                original = path.read_text() if path.exists() else None
                path.write_text("keep my work")
                with self.assertRaisesRegex(Waiting, "uncommitted changes"):
                    self.runner.switch_branch(self.first.id)
                self.assertEqual("main", git.current_branch(self.product))
                self.assertEqual("keep my work", path.read_text())
                if original is None:
                    path.unlink()
                else:
                    path.write_text(original)
        self.runner.switch_branch(self.first.id)
        self.assertEqual(self.branch, git.current_branch(self.product))

    def test_running_step_must_finish_before_switching(self):
        self.repo.transition(self.second.id, "play")
        record = self.repo.scan().valid[self.second.id]
        step = self.repo.step(record)
        self.assertTrue(self.runner.claim(record, step))
        with self.assertRaisesRegex(Waiting, "running steps"):
            self.runner.switch_branch(self.first.id)
        self.assertEqual("main", git.current_branch(self.product))
        self.runner.run_item(record, step, claimed=True)
        self.runner.switch_branch(self.first.id)
        self.assertEqual(self.tip, git.must(self.product, "rev-parse", "HEAD"))

    def test_tui_requires_dispatch_to_be_stopped_even_between_steps(self):
        app = tui.Backlog(self.repo, self.runner)
        app.shown = next(row for row in tui.rows(self.repo, self.runner) if row.key == self.first.id)
        notices = []
        app.notify = lambda message, **kwargs: notices.append(message)
        app.thread = threading.current_thread()
        app.action_switch_branch()
        self.assertEqual("main", git.current_branch(self.product))
        self.assertIn("Press s", notices[-1])
