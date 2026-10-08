"""Unit checks for path boundaries, masking and changed-line selection."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from devteam import config, git
from devteam.backlog import Repository
from devteam.evidence import PathGuard


class Masking(unittest.TestCase):
    def test_boundaries_and_idempotence(self):
        name = "fixture" + "person"
        checkout = Path("/home") / name / "product"
        guard = PathGuard(checkout)
        cases = [
            (f"Full output: {checkout}/tests/run.log", "Full output: tests/run.log"),
            (f"`/home/{name}/file`", "`<path>`"),
            (f"cwd=/Users/{name}/file", "cwd=<path>"),
            (f"/root/{name}/file", "<path>"),
            (f"/tmp/pytest-of-{name}/run", "<path>"),
            (f"GET /home/{name}", "GET <path>"),
            (f"Interpreter: {sys.executable}", "Interpreter: <path>"),
            (str(checkout), "."),
        ]
        for prefix in ["> ", ",", "[", "|", "@", "file://", "(", ":", "\""]:
            cases.append((f"{prefix}/home/{name}/file", prefix + "<path>"))
        for source, expected in cases:
            with self.subTest(source=source):
                masked, numbers = guard.mask(source)
                self.assertEqual(expected, masked)
                self.assertEqual([1], numbers)
                self.assertNotIn(name, masked)
                self.assertEqual((masked, []), guard.mask(masked))
        for source in ["src/root/app.py", "tests/root_test.py", "templates/home/index.html",
                       "https://example.com/home/news", "#!/usr/bin/env python", "/dev/null",
                       "/home/<name>", "/Users/<name>", "/root", "/home/", "GET /api/orders",
                       "/media/index.html", "x" + str(checkout),
                       "-I/home/" + name]:
            with self.subTest(source=source):
                self.assertEqual((source, []), guard.mask(source))

    def test_system_prefixes_are_exempt_and_literals_have_boundaries(self):
        with patch.object(sys, "prefix", "/usr"), patch.object(sys, "base_prefix", "/usr/local"), \
                patch.object(config, "ROOT", Path("/opt/harness")), \
                patch.object(sys, "executable", "/opt/python/bin/python"):
            guard = PathGuard()
        self.assertEqual(("/usr/bin/env /usr/local/lib", []), guard.mask("/usr/bin/env /usr/local/lib"))
        self.assertEqual(("<path> <path>", [1]), guard.mask("/opt/harness/a /opt/python/bin/python"))
        self.assertEqual(("/opt/harness-other", []), guard.mask("/opt/harness-other"))

    def test_story_criteria_fixture_does_not_trip(self):
        root = Path(__file__).resolve().parents[1]
        body = (root / "tests/fixtures/evidence/STORY-014-criteria.md").read_text()
        self.assertEqual((body, []), PathGuard(root).mask(body))


class CommitMasking(unittest.TestCase):
    def test_only_changed_lines_are_masked_with_originals_saved(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.com",
        }):
            root = Path(directory)
            subprocess.run(["git", "init", "-q", "-b", "devteam-backlog", str(root)], check=True)
            (root / ".gitignore").write_text("log/\n")
            stories = root / "stories"
            stories.mkdir()
            item = stories / "STORY-001.md"
            old = "/home/" + "previous" + "/record"
            fresh = "/home/" + "fixtureperson" + "/record"
            front = f"---\nid: STORY-001\ntitle: {fresh}\n---\n"
            item.write_text(front + old + "\n")
            git.commit_all(root, "existing")
            notices = []
            repo = Repository(root, guard=PathGuard(root.parent), notice=notices.append)
            item.write_text(front + old + "\nNew: " + fresh + "\n")
            (stories / "beside.txt").write_text(fresh)
            (root / "brief.md").write_text(fresh)
            (root / "binary").write_bytes(b"\xff")
            broken = stories / "STORY-002.md"
            broken.write_text("---\nid: BROKEN\n" + fresh)
            repo.commit("changed")
            self.assertEqual(front + old + "\nNew: <path>\n", item.read_text())
            self.assertEqual("---\nid: BROKEN\n<path>", broken.read_text())
            saved = list((root / "log" / "STORY-001").glob("unmasked-*.md"))
            self.assertEqual(1, len(saved))
            self.assertIn("New: " + fresh, saved[0].read_text())
            self.assertEqual(2, len(list((root / "log" / "unmasked").iterdir())))
            self.assertTrue(list((root / "log" / "STORY-002").glob("unmasked-*.md")))
            self.assertIn("masked lines 6", next(n for n in notices if "STORY-001" in n))
            patch_text = subprocess.run(["git", "-C", str(root), "show", "--format=", "HEAD"],
                                        capture_output=True).stdout.decode("utf-8", errors="replace")
            self.assertNotIn("+New: " + fresh, patch_text)
            self.assertFalse(any(p.startswith("log/") for p in git.must(root, "ls-files").splitlines()))
            count = len(notices)
            repo.commit("nothing")
            self.assertEqual(count, len(notices))


class ChangedFiles(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        identity = patch.dict(os.environ, {
            "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.com",
        })
        identity.start()
        self.addCleanup(identity.stop)
        git.must(self.root, "init", "-q", "-b", "devteam-backlog")
        (self.root / ".gitignore").write_text("log/\n")
        self.leak = "/home/" + "fixtureperson" + "/record"
        self.notices = []
        self.guard = PathGuard(self.root.parent)

    def test_staged_unstaged_renamed_and_untracked_files_only(self):
        for name in ["unchanged", "staged", "unstaged", "rename source", "deleted"]:
            (self.root / name).write_text("Earlier: " + self.leak + "\n")
        git.commit_all(self.root, "baseline")
        (self.root / "staged").write_text(self.leak)
        git.must(self.root, "add", "staged")
        (self.root / "unstaged").write_text(self.leak)
        git.must(self.root, "mv", "rename source", "renamed\tfile")
        (self.root / "untracked").write_text(self.leak)
        (self.root / "deleted").unlink()
        (self.root / "log").mkdir()
        (self.root / "log/ignored").write_text(self.leak)
        # Measure the real git calls; no collaborator's result is replaced.
        with patch("devteam.evidence.subprocess.run", wraps=subprocess.run) as runs:
            self.guard(self.root, self.notices.append)
        inspected = {call.args[0][-1] for call in runs.call_args_list if "show" in call.args[0]}
        self.assertEqual({"HEAD:staged", "HEAD:unstaged", "HEAD:renamed\tfile", "HEAD:untracked"}, inspected)
        self.assertIn(self.leak, (self.root / "unchanged").read_text())
        self.assertEqual(self.leak, (self.root / "log/ignored").read_text())
        for name in ["staged", "unstaged", "renamed\tfile", "untracked"]:
            self.assertNotIn(self.leak, (self.root / name).read_text())

    def test_unborn_branch_checks_staged_and_untracked_files(self):
        for name in ["staged", "untracked"]:
            (self.root / name).write_text(self.leak)
        git.must(self.root, "add", "staged")
        self.guard(self.root, self.notices.append)
        self.assertEqual("<path>", (self.root / "staged").read_text())
        self.assertEqual("<path>", (self.root / "untracked").read_text())

    def test_notice_when_backlog_is_outside_checkout(self):
        git.commit_all(self.root, "baseline")
        (self.root / "new").write_text(self.leak)
        checkout = self.root / "other-checkout"
        PathGuard(checkout)(self.root, self.notices.append)
        [saved] = (self.root / "log/unmasked").iterdir()
        self.assertIn(f"original saved to {os.path.relpath(saved, checkout)}", self.notices[0])
