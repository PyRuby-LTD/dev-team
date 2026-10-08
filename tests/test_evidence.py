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

    def test_story_body_does_not_trip(self):
        from devteam.backlog import parse
        root = Path(__file__).resolve().parents[1]
        path = root / "backlog/stories/STORY-014.md"
        body = parse(path, path.read_text()).body
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
