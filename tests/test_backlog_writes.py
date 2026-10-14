"""Backlog mutation isolation with real Git, threads and OS processes."""
from concurrent.futures import ThreadPoolExecutor
import multiprocessing
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from devteam import git
from devteam.backlog import Repository, WRITE, mutation
from devteam.config import load_roles
from devteam.evidence import PathGuard
from devteam.runner import Runner


def transition_process(root, item_id, ready, start, done):
    ready.set()
    if not start.wait(10):
        raise TimeoutError("start not signalled")
    Repository(root).transition(item_id, "analyse")
    done.set()


def hold_lock(root, ready, release):
    with mutation(Path(root)):
        ready.set()
        if not release.wait(20):
            raise TimeoutError("release not signalled")


class BacklogWrites(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.top = Path(temporary.name).resolve()
        identity = patch.dict(os.environ, {
            "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.com",
        })
        identity.start()
        self.addCleanup(identity.stop)
        git.must(self.top, "init", "-q", "-b", "main")
        (self.top / "README").write_text("Product\n")
        git.commit_all(self.top, "product")
        self.root = git.ensure_backlog(self.top)
        self.repo = Repository(self.root, guard=PathGuard(), notice=lambda _: None)
        self.epic = self.repo.create("epic", "Epic")
        self.story = self.repo.create("story", "First", parent=self.epic.id)
        self.other = self.repo.create("story", "Second", parent=self.epic.id)
        self.context = multiprocessing.get_context("spawn")

    def changes(self, ref="HEAD"):
        return git.must(self.root, "show", "--format=", "--name-only", ref).splitlines()

    def assert_isolated(self, record, message, ref="HEAD"):
        self.assertEqual([str(record.path.relative_to(self.root))], self.changes(ref))
        self.assertEqual(message, git.must(self.root, "show", "-s", "--format=%s", ref))

    def start_process(self, target, *args):
        process = self.context.Process(target=target, args=args)
        process.start()
        def cleanup():
            if process.is_alive():
                process.terminate()
            process.join(10)
        self.addCleanup(cleanup)
        return process

    def join_success(self, process):
        process.join(10)
        self.assertFalse(process.is_alive(), "mutation deadlocked")
        self.assertEqual(0, process.exitcode)

    def dirty_neighbours(self):
        leak = "/home/" + "fixtureperson" + "/record"
        with self.other.path.open("a") as handle:
            handle.write(leak)
        # Already staged changes must also stay out of another item's commit.
        git.must(self.root, "add", str(self.other.path))
        with self.epic.path.open("a") as handle:
            handle.write(leak)
        untracked = self.root / "unrelated.txt"
        untracked.write_text(leak)
        return {path: path.read_bytes() for path in (self.other.path, self.epic.path, untracked)}

    def assert_neighbours_unchanged(self, before):
        for path, text in before.items():
            self.assertEqual(text, path.read_bytes())
        self.assertEqual("stories/STORY-002.md", git.must(self.root, "diff", "--cached", "--name-only"))
        self.assertEqual("epics/EPIC-001.md", git.must(self.root, "diff", "--name-only"))
        self.assertIn("?? unrelated.txt", git.must(self.root, "status", "--porcelain"))

    def test_create_body_and_noted_transition_commit_only_their_item(self):
        before = self.dirty_neighbours()
        created = self.repo.create("story", "Third", parent=self.epic.id)
        self.assert_isolated(created, f"{created.id}: captured at captured")
        self.repo.write_body(self.story.id, "New: /home/fixtureperson/record\n", "body")
        self.assert_isolated(self.story, f"{self.story.id}: body")
        self.assertEqual("New: <path>\n", self.repo.scan().valid[self.story.id].body)
        self.repo.transition(self.story.id, "analyse", "Please investigate")
        self.assert_isolated(self.story, f"{self.story.id}: analyse -> analysis")
        self.assert_isolated(self.story, f"{self.story.id}: feedback for analyse", "HEAD~1")
        self.assert_neighbours_unchanged(before)

    def test_request_transition_leaves_revised_epic_uncommitted(self):
        request = self.repo.create("request", "Request")
        self.repo.transition(request.id, "analyse")
        self.repo.transition(request.id, "complete")
        self.repo.transition(request.id, "revise")
        before = {}

        def revise(role, prompt, cwd, extra_dir, log):
            before.update(self.dirty_neighbours())
            with request.path.open("a") as handle:
                handle.write("Revised request\n")
            log.write_text("fake transcript")
            return 0, "TRANSITION: complete"

        runner = Runner(self.repo, load_roles(), revise, report=lambda _: None)
        runner.run_pass()
        self.assertEqual({}, runner.failed)
        self.assert_isolated(request, f"{request.id}: complete -> review")
        self.assert_neighbours_unchanged(before)

    def test_two_processes_transition_with_separate_commits(self):
        start = self.context.Event()
        processes = []
        for record in (self.story, self.other):
            ready, done = self.context.Event(), self.context.Event()
            processes.append(self.start_process(transition_process, self.root, record.id, ready, start, done))
            self.assertTrue(ready.wait(10))
        start.set()
        for process in processes:
            self.join_success(process)
        commits = git.must(self.root, "log", "-2", "--format=%s").splitlines()
        self.assertEqual({f"{r.id}: analyse -> analysis" for r in (self.story, self.other)}, set(commits))
        by_id = {r.id: r for r in (self.story, self.other)}
        for ref, message in zip(("HEAD", "HEAD~1"), commits):
            self.assert_isolated(by_id[message.split(":")[0]], message, ref)

    def test_mutation_waits_for_lock_release_or_holder_death(self):
        for killed, record in zip((False, True), (self.story, self.other)):
            with self.subTest(killed=killed):
                ready, release = self.context.Event(), self.context.Event()
                holder = self.start_process(hold_lock, self.root, ready, release)
                self.assertTrue(ready.wait(10))
                attempted, start, done = (self.context.Event() for _ in range(3))
                start.set()
                writer = self.start_process(transition_process, self.root, record.id, attempted, start, done)
                self.assertTrue(attempted.wait(10))
                self.assertFalse(done.wait(0.3), "mutation bypassed held lock")
                self.assertEqual("captured", self.repo.scan().valid[record.id].metadata["step"])
                if killed:
                    holder.kill()
                    holder.join(10)
                else:
                    release.set()
                    self.join_success(holder)
                self.join_success(writer)
                self.assertTrue(done.is_set())

    def test_threads_use_write_and_nested_calls_do_not_deadlock(self):
        entered = threading.Event()
        done = threading.Event()
        def write():
            entered.set()
            self.repo.transition(self.story.id, "analyse", "Nested feedback")
            done.set()
        with ThreadPoolExecutor(max_workers=2) as pool:
            with WRITE:
                future = pool.submit(write)
                self.assertTrue(entered.wait(10))
                self.assertFalse(done.wait(0.3))
            future.result(timeout=10)
            futures = [pool.submit(Repository(self.root).create, "bug", "Concurrent") for _ in range(2)]
            records = [future.result(timeout=10) for future in futures]
        self.assertEqual({"BUG-001", "BUG-002"}, {record.id for record in records})
        self.assertEqual({}, self.repo.scan().errors)

    def test_lock_file_is_ignored_in_ensure_backlog_worktree(self):
        self.assertTrue((self.root / "log/backlog.lock").is_file())
        self.assertEqual("", git.must(self.root, "status", "--porcelain"))
        self.assertNotIn("log/backlog.lock", git.must(self.root, "ls-files").splitlines())
