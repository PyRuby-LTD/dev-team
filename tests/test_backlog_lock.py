"""The backlog write lock, across threads and OS processes."""
from concurrent.futures import ThreadPoolExecutor
import multiprocessing
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from devteam import git
from devteam.backlog import WRITE, mutation


def take_lock(root, attempted, done):
    attempted.set()
    with mutation(Path(root)):
        done.set()


def hold_lock(root, ready, release):
    with mutation(Path(root)):
        ready.set()
        if not release.wait(20):
            raise TimeoutError("release not signalled")


class BacklogLock(unittest.TestCase):
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
        self.context = multiprocessing.get_context("spawn")

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

    def test_mutation_waits_for_lock_release_or_holder_death(self):
        for killed in (False, True):
            with self.subTest(killed=killed):
                ready, release = self.context.Event(), self.context.Event()
                holder = self.start_process(hold_lock, self.root, ready, release)
                self.assertTrue(ready.wait(10))
                attempted, done = self.context.Event(), self.context.Event()
                writer = self.start_process(take_lock, self.root, attempted, done)
                self.assertTrue(attempted.wait(10))
                self.assertFalse(done.wait(0.3), "mutation bypassed held lock")
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
            with mutation(self.root), mutation(self.root):
                done.set()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with WRITE:
                future = pool.submit(write)
                self.assertTrue(entered.wait(10))
                self.assertFalse(done.wait(0.3))
            future.result(timeout=10)
        self.assertTrue(done.is_set())

    def test_lock_file_is_ignored_in_ensure_backlog_worktree(self):
        with mutation(self.root):
            pass
        self.assertTrue((self.root / "log/backlog.lock").is_file())
        self.assertEqual("", git.must(self.root, "status", "--porcelain"))
        self.assertNotIn("log/backlog.lock", git.must(self.root, "ls-files").splitlines())


if __name__ == "__main__":
    unittest.main()
