import re
import sys
import time
import unittest

from devteam import git
from devteam.tryout import group_alive
from tests import test_checkout as fixtures


class Tryout(unittest.TestCase):
    def engine(self, role, prompt, cwd, extra_dir, log):
        item = re.search(r"/(STORY-[0-9]+)\.md", prompt)[1]
        self.calls.append((item, role.name, prompt, cwd, git.current_branch(self.product)))
        log.write_text("transcript")
        if role.name == "implementer":
            (cwd / f"{item}.txt").write_text("change\n")
            return 0, "TRANSITION: implemented"
        return 0, "TRANSITION: approve"

    def setUp(self):
        fixtures.CheckoutAcceptance.setUp(self)
        self.repo.transition(self.first.id, "play")
        self.runner.run(once=True)
        self.claim = self.runner.tryout
        self.claim.command = [sys.executable, "-u", "-c", "import time; print('product ready'); time.sleep(60)"]
        self.addCleanup(self.release)

    def release(self):
        worker = self.claim.release()
        if worker:
            worker.join(8)
            self.assertFalse(worker.is_alive())

    def wait_for(self, condition):
        deadline = time.monotonic() + 5
        while not condition():
            if time.monotonic() > deadline:
                self.fail("timed out")
            time.sleep(0.01)

    def queue(self):
        self.repo.transition(self.second.id, "play")
        record = self.repo.scan().valid[self.second.id]
        self.runner.take_checkout(record)
        (self.product / "saved.txt").write_text("earlier work")
        git.commit_all(self.product, "earlier work")
        third = self.repo.create("story", "Queued", parent=self.epic.id)
        self.repo.transition(third.id, "play")
        return record, third

    def test_stopped_agents_grant_immediately_log_output_and_retain_claim_after_exit(self):
        self.claim.command = [sys.executable, "-u", "-c", "print('product ready')"]
        self.assertTrue(self.claim.request(self.first.id))
        self.assertEqual(f"devteam/{self.first.id}", git.current_branch(self.product))
        self.wait_for(lambda: self.claim.process.poll() is not None)
        self.claim.tick()
        self.assertIn("product exited (0)", self.claim.status)
        self.assertEqual(self.first.id, self.claim.item_id)
        logs = list((self.backlog / "log" / self.first.id).glob("run-*.log"))
        self.assertIn("product ready", logs[0].read_text())

    def test_refuses_wrong_step_and_second_request_without_changing_claim(self):
        self.assertFalse(self.claim.request(self.second.id))
        self.assertIsNone(self.claim.item_id)
        self.assertIn("only at accept or pull-request", self.messages[-1])
        self.assertTrue(self.claim.request(self.first.id))
        process = self.claim.process
        self.assertFalse(self.claim.request(self.second.id))
        self.assertIs(process, self.claim.process)
        self.assertIn("release it first", self.messages[-1])

    def test_request_waits_for_running_step_then_preempts_and_restores_interrupted_story(self):
        record, third = self.queue()
        self.assertTrue(self.runner.claim(record, self.repo.step(record)))
        self.claim.request(self.first.id)
        self.assertIsNone(self.claim.process)
        self.assertEqual(f"devteam/{record.id}", git.current_branch(self.product))
        self.runner.run_item(record, self.repo.step(record), claimed=True)
        self.assertIsNotNone(self.claim.process)
        self.assertEqual(record.id, self.claim.interrupted)
        self.assertEqual(0, self.runner.run_pass())
        self.release()
        self.calls.clear()
        self.runner.run_pass()
        self.assertEqual([(record.id, "reviewer")], [(c[0], c[1]) for c in self.calls])
        self.assertEqual("earlier work", (self.product / "saved.txt").read_text())
        self.assertEqual(f"devteam/{record.id}", git.current_branch(self.product))
        self.runner.run_pass()
        self.assertEqual(third.id, self.calls[-1][0])

    def test_dirty_failed_step_waits_preserves_work_and_cancel_does_not_switch(self):
        record, _ = self.queue()
        self.runner.engine = lambda *args: (9, "")
        (self.product / "app.txt").write_text("failed work")
        self.runner.run_item(record, self.repo.step(record))
        self.assertIn(record.id, self.runner.failed)
        self.claim.request(self.first.id)
        self.assertIsNone(self.claim.process)
        self.assertIn("uncommitted changes", self.claim.status)
        self.assertEqual("failed work", (self.product / "app.txt").read_text())
        self.release()
        self.assertEqual(f"devteam/{record.id}", git.current_branch(self.product))
        self.claim.request(self.first.id)
        git.must(self.product, "restore", "app.txt")
        self.claim.tick()
        self.assertIsNotNone(self.claim.process)
        self.assertIsNone(self.claim.interrupted)
        self.release()
        self.runner.engine = self.engine
        self.runner.run_pass()
        self.assertEqual("STORY-003", git.current_branch(self.product).removeprefix("devteam/"))

    def test_exhausted_story_does_not_get_priority_on_release(self):
        record, third = self.queue()
        self.runner._runs[record.id] = self.runner.max_runs
        self.claim.request(self.first.id)
        self.assertIsNone(self.claim.interrupted)
        self.release()
        # Exhausted A fails its ordinary attempt; it never holds B's queue.
        self.runner.run_pass()
        self.runner.run_pass()
        self.assertEqual(f"devteam/{third.id}", git.current_branch(self.product))

    def test_stopped_story_keeps_priority_and_revision_keeps_earlier_commits(self):
        record, _ = self.queue()
        self.claim.request(self.first.id)
        self.assertEqual(record.id, self.claim.interrupted)
        self.release()
        self.runner.run_pass()
        self.assertEqual(f"devteam/{record.id}", git.current_branch(self.product))
        self.assertEqual("earlier work", (self.product / "saved.txt").read_text())
        self.runner.run(once=True)
        self.repo.transition(self.first.id, "revise")
        self.runner.run(once=True)
        self.assertIn("STORY-001: implement by implementer", git.must(self.product, "log", "--format=%s"))
        self.assertTrue((self.product / "STORY-001.txt").exists())

    def test_missing_makefile_target_and_program_release_claim(self):
        for command, contents in [(["make", "run"], None), (["make", "run"], ".PHONY: run\nall:\n\ttrue\n"),
                                  (["/no-such-product-program"], None)]:
            with self.subTest(command=command, contents=contents):
                if contents:
                    (self.product / "Makefile").write_text(contents)
                    git.commit_all(self.product, "Makefile without target")
                self.claim.command = command
                self.claim.request(self.first.id)
                self.assertIsNone(self.claim.item_id)
                self.assertIsNone(self.claim.process)
                self.assertIn("cannot run product", self.messages[-1])
        self.repo.transition(self.second.id, "play")
        self.runner.run_pass()
        self.assertEqual(f"devteam/{self.second.id}", git.current_branch(self.product))

    def test_make_target_and_nonzero_exit_are_a_started_product(self):
        (self.product / "Makefile").write_text("run:\n\t@echo started; exit 4\n")
        git.commit_all(self.product, "run target")
        self.claim.command = ["make", "run"]
        self.claim.request(self.first.id)
        self.wait_for(lambda: self.claim.process.poll() is not None)
        self.claim.tick()
        self.assertTrue(self.claim.exited)
        self.assertIsNotNone(self.claim.item_id)
        self.assertFalse(any("cannot run product" in m for m in self.messages))

    def test_invalid_checkout_releases_claim_and_allows_queued_work_after_repair(self):
        for checkout in ("detached", "missing base"):
            with self.subTest(checkout=checkout):
                git.must(self.product, "switch", "-q", "main")
                if checkout == "detached":
                    git.must(self.product, "checkout", "-q", "--detach")
                    reason = "the checkout is not on a branch"
                else:
                    git.must(self.product, "switch", "-q", "-c", "devteam/unrecorded")
                    reason = "no base branch is recorded for devteam/unrecorded"
                self.claim.request(self.first.id)
                self.assertIsNone(self.claim.item_id)
                self.assertIsNone(self.claim.process)
                self.assertIn("cannot run product", self.messages[-1])
                self.assertIn(reason, self.messages[-1])
                self.claim.tick()
                git.must(self.product, "switch", "-q", "main")
        self.repo.transition(self.second.id, "play")
        self.assertEqual(1, self.runner.run_pass())
        self.assertEqual(f"devteam/{self.second.id}", git.current_branch(self.product))

    def test_checkout_becoming_dirty_during_grant_keeps_request_waiting(self):
        take_checkout = self.runner.take_checkout

        def dirty_then_take(record, tryout=False):
            (self.product / "app.txt").write_text("customer work")
            return take_checkout(record, tryout=tryout)

        git.must(self.product, "switch", "-q", "main")
        self.runner.take_checkout = dirty_then_take
        self.claim.request(self.first.id)
        self.assertEqual(self.first.id, self.claim.item_id)
        self.assertIsNone(self.claim.process)
        self.assertIn("uncommitted changes", self.claim.status)
        self.assertEqual("customer work", (self.product / "app.txt").read_text())
        self.runner.take_checkout = take_checkout
        git.must(self.product, "restore", "app.txt")
        self.claim.tick()
        self.assertIsNotNone(self.claim.process)

    def test_transition_cancels_pending_request_and_releases_running_product(self):
        (self.product / "app.txt").write_text("dirty")
        self.claim.request(self.first.id)
        self.repo.transition(self.first.id, "revise")
        self.assertIsNone(self.claim.item_id)
        git.must(self.product, "restore", "app.txt")
        self.runner.run(once=True)
        self.claim.request(self.first.id)
        process = self.claim.process
        self.repo.transition(self.first.id, "accept")
        self.wait_for(lambda: self.claim.item_id is None)
        self.assertIsNotNone(process.poll())

    def test_release_holds_dirty_checkout_steps_until_customer_cleans(self):
        self.claim.request(self.first.id)
        (self.product / "product-output.txt").write_text("keep me")
        self.release()
        self.assertIn("uncommitted changes; checkout steps wait", self.claim.status)
        self.repo.transition(self.second.id, "play")
        self.assertEqual(0, self.runner.run_pass())
        self.assertEqual("keep me", (self.product / "product-output.txt").read_text())
        (self.product / "product-output.txt").unlink()
        self.assertEqual(1, self.runner.run_pass())

    def test_release_is_nonblocking_and_kills_stubborn_parent_and_child(self):
        self.claim.command = [sys.executable, "-u", "-c", """
import os, signal, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
pid = os.fork()
print('ready', os.getpid(), flush=True)
while True: time.sleep(1)
"""]
        self.claim.request(self.first.id)
        process = self.claim.process
        logs = list((self.backlog / "log" / self.first.id).glob("run-*.log"))
        self.wait_for(lambda: sum(line.startswith("ready ") for line in logs[0].read_text().splitlines()) == 2)
        started = time.monotonic()
        worker = self.claim.release()
        self.assertLess(time.monotonic() - started, 1)
        self.assertIsNotNone(self.claim.item_id)
        self.assertIn("stopping", self.claim.status)
        worker.join(8)
        self.assertFalse(worker.is_alive())
        self.assertGreaterEqual(time.monotonic() - started, 5)
        self.assertFalse(group_alive(process.pid))
        self.assertIsNone(self.claim.item_id)

    def test_noncheckout_steps_still_run_during_tryout(self):
        self.claim.request(self.first.id)
        self.repo.transition(self.second.id, "analyse")
        original = self.runner.engine
        self.runner.engine = lambda *args: (0, "TRANSITION: ready")
        self.assertEqual(1, self.runner.run_pass())
        self.assertEqual("ready", self.repo.scan().valid[self.second.id].metadata["step"])
        self.assertIsNone(self.claim.process.poll())
        self.assertEqual(f"devteam/{self.first.id}", git.current_branch(self.product))
        self.runner.engine = original

    def test_exited_parent_does_not_leave_its_child_alive_on_release(self):
        self.claim.command = [sys.executable, "-u", "-c", """
import os, time
if os.fork() == 0:
    print('child ready', flush=True)
    time.sleep(60)
"""]
        self.claim.request(self.first.id)
        process = self.claim.process
        self.wait_for(lambda: process.poll() is not None)
        self.claim.tick()
        self.assertTrue(self.claim.exited)
        self.assertTrue(group_alive(process.pid))
        self.release()
        self.assertFalse(group_alive(process.pid))
