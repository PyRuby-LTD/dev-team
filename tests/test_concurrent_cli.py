"""STORY-019: concurrent dev-team processes commit only their own item.

Two real command-line processes move different stories at the same moment while another item has an
uncommitted edit holding a machine path. Each commit must hold exactly its own item's file.
"""
import subprocess
import sys

from tests.test_run_evidence import HOME, ROOT, Product


class ConcurrentBacklogCommits(Product):
    def backlog_git(self, *args):
        return self.git(self.backlog, *args)

    def test_parallel_moves_commit_only_their_own_item_and_leave_neighbours_alone(self):
        self.devteam("backlog", "capture", "story", "Second", "--id", "STORY-002", "--parent", "EPIC-001")
        epic = self.backlog / "epics" / "EPIC-001.md"
        epic.write_text(epic.read_text() + "\nRevised in " + HOME + "/work\n")
        stray = self.backlog / "stray.txt"
        stray.write_text("scratch " + HOME + "\n")
        epic_before, stray_before = epic.read_bytes(), stray.read_bytes()
        head = self.backlog_git("rev-parse", "HEAD").strip()

        command = [sys.executable, "-m", "devteam", "--product", str(self.product), "backlog", "move"]
        processes = [subprocess.Popen([*command, item, "analyse"], cwd=ROOT, env=self.environment(),
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                     for item in ("STORY-001", "STORY-002")]
        for process in processes:
            output, _ = process.communicate(timeout=120)
            self.assertEqual(0, process.returncode, output)

        commits = self.backlog_git("log", "--format=%H", head + "..HEAD").split()
        self.assertEqual(2, len(commits))
        seen = {}
        for commit in commits:
            lines = self.backlog_git("show", "--name-only", "--format=%s", commit).strip().splitlines()
            seen[lines[0].split(":")[0]] = [line for line in lines[1:] if line]
        self.assertEqual({"STORY-001": ["stories/STORY-001.md"], "STORY-002": ["stories/STORY-002.md"]}, seen)
        self.assertEqual(epic_before, epic.read_bytes())
        self.assertEqual(stray_before, stray.read_bytes())
        status = self.backlog_git("status", "--porcelain")
        self.assertIn("epics/EPIC-001.md", status)
        self.assertIn("stray.txt", status)
        self.assertNotIn("STORY-00", status)
        self.assertTrue((self.backlog / "log" / "backlog.lock").exists())
        self.assertNotIn("backlog.lock", self.backlog_git("ls-files"))
