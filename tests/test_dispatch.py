"""Event-controlled workers exercise concurrency without running external agents."""
import json
from pathlib import Path
import tempfile
import threading
import unittest

from devteam import git
from devteam.backlog import Repository
from devteam.runner import Runner, StepFailed
from tests.test_runner import role

WORKFLOW = {
    "initial": "ready",
    "steps": {
        "ready": {"owner": "human", "transitions": {
            "analyse": "analysis", "play": "implement",
            "merge": "merged", "reject": "rejected"}},
        "analysis": {"owner": "agent:analyst", "transitions": {"finished": "done"}},
        "implement": {"owner": "agent:implementer", "transitions": {"finished": "done"}},
        "merged": {"owner": "harness:merged", "transitions": {"completed": "done"}},
        "rejected": {"owner": "harness:rejected", "transitions": {"completed": "done"}},
        "done": {"owner": "human", "transitions": {}},
    },
}


class Dispatch(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        workflows = self.root / "workflows"
        workflows.mkdir()
        (workflows / "default.json").write_text(json.dumps(WORKFLOW))
        self.product = self.root / "product"
        self.product.mkdir()
        git.must(self.product, "init", "-q", "-b", "main")
        git.must(self.product, "config", "user.name", "test")
        git.must(self.product, "config", "user.email", "test@test")
        git.must(self.product, "commit", "-q", "--allow-empty", "-m", "initial")
        self.roles = {"analyst": role("analyst"), "implementer": role("implementer", True)}
        self.repo = Repository(self.root / "backlog", workflows, self.roles)
        self.epic = self.repo.create("epic", "Epic")
        self.started = {}
        self.release = threading.Event()
        self.calls = []
        self.messages = []
        self.runner = Runner(self.repo, self.roles, self.engine, self.messages.append, checkout=self.product)
        self.futures = []
        self.loops = []
        self.addCleanup(self.drain)

    def drain(self):
        for stop, thread in self.loops:
            stop.set()
            thread.join(2)
        self.release.set()
        for future in self.futures:
            future.result(timeout=5)
        # Continuous loops own their futures; wait for those workers too.
        deadline = threading.Event()
        for _ in range(500):
            if not self.runner.active_ids():
                break
            deadline.wait(.01)
        self.assertEqual([], self.runner.active_ids())

    def item(self, transition):
        record = self.repo.create("story", "Item", parent=self.epic.id)
        self.started[record.id] = threading.Event()
        return self.repo.transition(record.id, transition)

    def engine(self, role, prompt, cwd, extra_dir, log, on_line=None):
        item_id = log.parent.name
        self.calls.append(item_id)
        self.started[item_id].set()
        if on_line is not None:
            on_line("live")
        if not self.release.wait(5):
            raise RuntimeError("test did not release engine")
        return 0, "TRANSITION: finished"

    def dispatch(self):
        submitted = self.runner.dispatch()
        self.futures.extend(submitted)
        return submitted

    def loop(self, once=False):
        stop = threading.Event()
        thread = threading.Thread(target=self.runner.run,
                                  kwargs={"stop": stop, "interval": .01, "once": once})
        self.loops.append((stop, thread))
        thread.start()
        return stop, thread

    def test_two_and_four_agents_start_together_without_duplicate_steps(self):
        for count in (2, 4):
            with self.subTest(count=count):
                self.release.clear()
                records = [self.item("analyse") for _ in range(count)]
                submitted = self.dispatch()
                for record in records:
                    self.assertTrue(self.started[record.id].wait(2))
                self.assertEqual(sorted(record.id for record in records), self.runner.active_ids())
                snapshot = self.runner.active_ids()
                snapshot.clear()
                self.assertEqual(count, len(self.runner.active_ids()))
                self.assertEqual([], self.dispatch())
                self.assertEqual(0, self.runner.run_pass())
                self.release.set()
                self.assertEqual(count, sum(f.result(timeout=3) for f in submitted))
                self.assertEqual(count, sum(self.calls.count(record.id) for record in records))
        self.assertNotIn("max_agents", (Path(__file__).resolve().parent.parent / "config/roles.toml").read_text())

    def test_branch_steps_exclude_each_other_but_allow_analysis(self):
        self.release.clear()
        holder = self.item("play")
        other = self.item("play")
        analyst = self.item("analyse")
        submitted = self.dispatch()
        self.assertTrue(self.started[holder.id].wait(2))
        self.assertTrue(self.started[analyst.id].wait(2))
        self.assertFalse(self.started[other.id].is_set())
        self.assertEqual(f"waiting for {holder.id}, which is using the checkout",
                         self.runner.waiting[other.id])
        self.assertEqual({}, self.runner.failed)
        self.assertEqual(f"devteam/{holder.id}", git.current_branch(self.product))
        self.release.set()
        self.assertEqual(2, sum(f.result(timeout=3) for f in submitted))
        self.assertEqual(1, self.runner.run_pass())

    def test_continuous_headless_dispatch_starts_new_work_and_stop_does_not_join(self):
        first = self.item("analyse")
        stop, thread = self.loop()
        self.assertTrue(self.started[first.id].wait(2))
        other = self.item("analyse")
        self.assertTrue(self.started[other.id].wait(2))
        stop.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual([first.id, other.id], self.runner.active_ids())
        later = self.item("analyse")
        stop, thread = self.loop()
        self.assertTrue(self.started[later.id].wait(2))
        self.assertEqual(1, self.calls.count(first.id))
        self.assertEqual(1, self.calls.count(other.id))

    def test_expected_and_unexpected_failures_do_not_stop_other_workers(self):
        for failure in (StepFailed("expected"), RuntimeError("unexpected")):
            with self.subTest(failure=failure):
                bad = self.item("analyse")
                good = self.item("analyse")
                normal = self.engine

                def failing(role, prompt, cwd, extra_dir, log):
                    if log.parent.name == bad.id:
                        raise failure
                    return normal(role, prompt, cwd, extra_dir, log)

                self.runner.engine = failing
                self.release.clear()
                submitted = self.dispatch()
                self.assertTrue(self.started[good.id].wait(2))
                self.release.set()
                self.assertEqual(2, sum(f.result(timeout=3) for f in submitted))
                self.assertEqual(str(failure), self.runner.failed[bad.id])
                self.assertTrue(any(bad.id in message and str(failure) in message for message in self.messages))
                self.assertEqual(0, self.runner.run_pass())
                self.runner.retry(bad.id)
                self.runner.engine = normal
                self.assertEqual(1, self.runner.run_pass())

    def test_exhausted_checkout_steps_wait_for_dirty_work_before_enforcing_limit(self):
        self.runner.max_runs = 0
        for transition in ("play",):
            with self.subTest(transition=transition):
                record = self.item(transition)
                step = self.repo.step(record)
                dirty = self.product / "local-work.txt"
                dirty.write_text("keep this work\n")
                self.assertFalse(self.runner.run_item(record, step))
                self.assertIn("uncommitted changes", self.runner.waiting[record.id])
                self.assertNotIn(record.id, self.runner.failed)
                self.assertEqual("keep this work\n", dirty.read_text())
                dirty.unlink()
                self.assertTrue(self.runner.run_item(record, step))
                self.assertEqual(f"devteam/{record.id}", git.current_branch(self.product))
                self.assertIn("already ran 0 steps", self.runner.failed[record.id])
                self.assertNotIn(record.id, self.runner.runs)
                self.assertEqual([], self.calls)
                git.must(self.product, "switch", "-q", "main")

    def test_count_run_is_atomic_and_enforces_limit(self):
        record = self.item("analyse")
        self.runner.max_runs = 100
        barrier = threading.Barrier(9)
        failures = []

        def count():
            barrier.wait()
            for _ in range(25):
                try:
                    self.runner.count_run(record)
                except StepFailed:
                    failures.append(1)

        threads = [threading.Thread(target=count) for _ in range(8)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(2)
        self.assertEqual(100, self.runner.runs[record.id])
        self.assertEqual(100, len(failures))

    def test_once_drains_all_submissions_and_returns_for_waiting_items(self):
        first = self.item("analyse")
        other = self.item("play")
        waiting = self.item("play")
        stop, thread = self.loop(once=True)
        self.assertTrue(self.started[first.id].wait(2))
        self.assertTrue(self.started[other.id].wait(2))
        self.assertTrue(thread.is_alive())
        self.release.set()
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual("done", self.repo.scan().valid[waiting.id].metadata["step"])
        # A human step releases its branch even though it is unfinished.
        holder = self.repo.create("story", "Human holder", parent=self.epic.id)
        self.runner.take_checkout(holder)
        blocked = self.item("play")
        stop, thread = self.loop(once=True)
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertNotIn(blocked.id, self.runner.waiting)
        self.assertEqual("done", self.repo.scan().valid[blocked.id].metadata["step"])

    def test_once_dispatches_work_unlocked_by_a_completion_while_another_worker_runs(self):
        first = self.item("analyse")
        second = self.item("analyse")
        later = self.repo.create("story", "Later", parent=self.epic.id)
        self.started[later.id] = threading.Event()
        normal = self.engine

        def unlock(role, prompt, cwd, extra_dir, log):
            if log.parent.name == second.id:
                self.repo.transition(later.id, "analyse")
                return 0, "TRANSITION: finished"
            return normal(role, prompt, cwd, extra_dir, log)

        self.runner.engine = unlock
        stop, thread = self.loop(once=True)
        self.assertTrue(self.started[first.id].wait(2))
        self.assertTrue(self.started[later.id].wait(2))
        self.assertTrue(thread.is_alive())
        self.release.set()
        thread.join(3)
        self.assertFalse(thread.is_alive())

    def test_parallel_non_branch_file_is_included_in_branch_commit(self):
        branch = self.item("play")
        analyst = self.item("analyse")
        written = threading.Event()
        entered = threading.Event()
        normal = self.engine

        def writing(role, prompt, cwd, extra_dir, log):
            if log.parent.name == analyst.id:
                self.assertTrue(entered.wait(2))
                (cwd / "stray.txt").write_text("parallel file")
                written.set()
            else:
                entered.set()
                self.assertTrue(written.wait(2))
            return normal(role, prompt, cwd, extra_dir, log)

        self.runner.engine = writing
        submitted = self.dispatch()
        self.assertTrue(self.started[branch.id].wait(2))
        self.assertTrue(self.started[analyst.id].wait(2))
        self.release.set()
        self.assertEqual(2, sum(f.result(timeout=3) for f in submitted))
        self.assertEqual("parallel file", git.must(self.product, "show", "HEAD:stray.txt"))
        self.assertEqual(f"devteam/{branch.id}", git.current_branch(self.product))

