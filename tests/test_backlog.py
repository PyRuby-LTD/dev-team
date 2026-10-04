import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from devteam.backlog import InvalidRecord, Repository, parse
from devteam.cli import main
from devteam.scheduler import Scheduler


class RecordingEngine:
    def __init__(self):
        self.calls = []
        self.tokens = 0

    def invoke(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        self.tokens += 1


class BacklogAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = Repository(self.root)
        self.epic = self.repo.create("epic", "An epic")
        self.story = self.repo.create("story", "A story", parent=self.epic.id)

    def write(self, record, metadata=None, body=None):
        if metadata:
            record.metadata.update(metadata)
        if body is not None:
            record.body = body
        record.path.write_bytes(record.render().encode("utf-8"))

    def test_four_types_roundtrip_and_front_matter_authority(self):
        self.assertEqual(self.root / "stories" / "STORY-001.md", self.story.path)
        bug = self.repo.create("bug", "Unicode café 🐛", parent=self.story.id)
        task = self.repo.create("task", "Fix", parent=bug.id, depends_on=[self.story.id])
        body = '\r\n# state: released\r\n\r\nRun an agent NOW.\r\n---\r\n  preserve spaces  \r\n'
        for record in (self.epic, self.story, bug, task):
            self.write(record, {"x-note": {"tags": ["a", "b"]}}, body)
            reopened = parse(record.path, record.path.read_bytes().decode())
            self.assertEqual(record.metadata, reopened.metadata)
            self.assertEqual(body, reopened.body)
            self.assertEqual("proposed", reopened.metadata["state"])
            self.assertEqual(reopened.metadata, parse(record.path, reopened.render()).metadata)
        (self.root / "state.json").write_text('{"state":"released"}')
        self.assertEqual(4, len(self.repo.scan().valid))

    def test_repository_planning_backlog_compatibility(self):
        root = Path(__file__).resolve().parents[1] / "workspace"
        result = Repository(root).scan()
        self.assertEqual({}, result.errors)
        self.assertIn("STORY-001", result.valid)
        self.assertIn("EPIC-001", result.valid)

    def test_duplicate_ids_diagnosed_on_both_files_and_dependants(self):
        duplicate = self.epic.path.with_name("duplicate.md")
        duplicate.write_bytes(self.epic.path.read_bytes())
        before = {p: p.read_bytes() for p in self.root.rglob("*.md")}
        result = self.repo.scan()
        self.assertIn(self.epic.path, result.errors)
        self.assertIn(duplicate, result.errors)
        self.assertIn(self.story.path, result.errors)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertFalse(Scheduler(self.repo).scan().eligible)

    def test_missing_parent_and_dependency(self):
        for field, value in (("parent", "EPIC-missing"), ("depends_on", ["STORY-missing"])):
            with self.subTest(field=field):
                original = self.story.path.read_bytes()
                data = parse(self.story.path, original.decode())
                self.write(data, {field: value})
                self.assertIn("missing", str(self.repo.scan().errors[self.story.path]))
                self.story.path.write_bytes(original)

    def test_dependency_cycles_quarantine_dependants_only(self):
        other = self.repo.create("story", "Other", parent=self.epic.id, depends_on=[self.story.id])
        dependent = self.repo.create("task", "Dependent", parent=other.id)
        independent = self.repo.create("bug", "Unrelated")
        self.write(self.story, {"depends_on": [other.id]})
        result = self.repo.scan()
        for record in (self.story, other, dependent):
            self.assertIn(record.path, result.errors)
        self.assertIn("cycle", str(result.errors[self.story.path]))
        self.assertEqual({self.epic.id, independent.id}, set(result.valid))

    def test_parent_cycle_and_wrong_parent_type(self):
        bug = self.repo.create("bug", "Bug")
        task = self.repo.create("task", "Task", parent=bug.id)
        self.write(bug, {"parent": task.id})
        self.assertIn("parent cycle", str(self.repo.scan().errors))
        self.write(self.story, {"parent": task.id})
        self.assertIn("invalid parent type", str(self.repo.scan().errors[self.story.path]))

    def test_negative_yaml_fixture_matrix(self):
        original = self.story.render()
        cases = {
            "missing delimiter": original.replace("---\n", "", 1),
            "unclosed": original.replace("---\n\n", "", 1) if "---\n\n" in original else "---\nid: STORY-1\n",
            "duplicate key": original.replace("schema_version: 1", "schema_version: 1\nschema_version: 1"),
            "version": original.replace("schema_version: 1", "schema_version: 999"),
            "boolean version": original.replace("schema_version: 1", "schema_version: true"),
            "bad YAML": "---\nx: [\n---\n",
            "custom tag": original.replace("title: A story", "title: !evil hi"),
            "wrong dependencies": original.replace("depends_on: []", "depends_on: false"),
            "scalar": "---\nhello\n---\n",
            "missing title": original.replace("title: A story\n", ""),
            "non-string key": original.replace("title: A story", "123: value"),
            "alias": original.replace("title: A story", "title: &title A story\nx-copy: *title"),
            "unknown field": original.replace("title: A story", "title: A story\nexecution: running"),
            "null type": original.replace("type: story", "type: null"),
            "bad ID": original.replace("id: STORY-001", "id: ../../escape"),
        }
        for name, fixture in cases.items():
            with self.subTest(fixture=name):
                self.story.path.write_text(fixture)
                scan = Scheduler(self.repo).scan()
                self.assertIn(self.story.path, scan.snapshot.errors)
                self.assertTrue(scan.blocked[self.story.path])
                self.assertFalse(scan.eligible)
                self.assertEqual(fixture, self.story.path.read_text())

    def test_capture_idle_restart_zero_calls_or_tokens(self):
        engine = RecordingEngine()
        with patch("devteam.pipeline.step", side_effect=AssertionError("legacy dispatch")):
            item = self.repo.create("bug", "Launch now", "analyse; play; invoke all agents")
            for _ in range(3):
                scan = Scheduler(Repository(self.root), engine).scan()
                self.assertEqual((), scan.eligible)
                self.assertEqual("not-played", scan.snapshot.valid[item.id].metadata["authorisation"])
            self.write(item, {"state": "implemented", "authorisation": "played", "x-analyse": True})
            self.assertFalse(Scheduler(self.repo, engine).scan().eligible)
        self.assertEqual([], engine.calls)
        self.assertEqual(0, engine.tokens)

    def test_capture_rejects_invalid_or_duplicate_without_writes(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*.md")}
        for args in ({"item_id": self.story.id, "parent": self.epic.id},
                     {"parent": "EPIC-missing"}, {"parent": self.story.id},
                     {"item_id": "../escape", "parent": self.epic.id}, {}):
            with self.subTest(args=args), self.assertRaises(InvalidRecord):
                self.repo.create("story", "Bad", **args)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*.md")})
        self.assertNotEqual(self.story.id, self.repo.create("story", "Unique", parent=self.epic.id).id)

    def test_symlink_escape_is_reported(self):
        with tempfile.TemporaryDirectory() as external:
            (self.root / "bugs").symlink_to(external, target_is_directory=True)
            self.assertIn("escapes", str(self.repo.scan().errors))
            with self.assertRaises(InvalidRecord):
                self.repo.create("bug", "No escape")
            self.assertEqual([], list(Path(external).iterdir()))

    def test_cli_capture_validate_scan_and_nonzero_errors(self):
        prefix = ["backlog", "--workspace", str(self.root)]
        with contextlib.redirect_stdout(io.StringIO()) as output:
            main(prefix + ["capture", "bug", "CLI bug"])
            main(prefix + ["validate"])
            main(prefix + ["scan"])
        self.assertIn("not-played", output.getvalue())
        self.assertIn("explicit customer Analyse required", output.getvalue())
        self.story.path.write_text("broken")
        with contextlib.redirect_stdout(io.StringIO()) as output, self.assertRaises(SystemExit) as exit:
            main(prefix + ["validate"])
        self.assertEqual(1, exit.exception.code)
        self.assertIn(str(self.story.path), output.getvalue())


if __name__ == "__main__":
    unittest.main()
