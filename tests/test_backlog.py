import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from devteam.backlog import InvalidRecord, Repository, parse
from devteam.cli import main


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
        bug = self.repo.create("bug", "Unicode café \U0001f41b", parent=self.story.id)
        task = self.repo.create("task", "Fix", parent=bug.id)
        body = '\r\n# step: done\r\n\r\nRun an agent NOW.\r\n---\r\n  preserve spaces  \r\n'
        for record in (self.epic, self.story, bug, task):
            self.write(record, body=body)
            reopened = parse(record.path, record.path.read_bytes().decode())
            self.assertEqual(record.metadata, reopened.metadata)
            self.assertEqual(body, reopened.body)
            self.assertEqual(reopened.metadata, parse(record.path, reopened.render()).metadata)
        (self.root / "state.json").write_text('{"step":"done"}')
        self.assertEqual(4, len(self.repo.scan().valid))

    def test_capture_sets_workflow_and_initial_step_except_on_epics(self):
        self.assertEqual({"id": "EPIC-001", "type": "epic", "title": "An epic"}, self.epic.metadata)
        self.assertEqual("default", self.story.metadata["workflow"])
        self.assertEqual("captured", self.story.metadata["step"])

    def test_repository_backlog_is_valid(self):
        root = Path(__file__).resolve().parents[1] / "workspace"
        result = Repository(root).scan()
        self.assertEqual({}, result.errors)
        self.assertIn("STORY-001", result.valid)
        self.assertIn("EPIC-001", result.valid)

    def test_duplicate_ids_diagnosed_on_both_files_and_children(self):
        duplicate = self.epic.path.with_name("duplicate.md")
        duplicate.write_bytes(self.epic.path.read_bytes())
        before = {p: p.read_bytes() for p in self.root.rglob("*.md")}
        result = self.repo.scan()
        self.assertIn(self.epic.path, result.errors)
        self.assertIn(duplicate, result.errors)
        self.assertIn(self.story.path, result.errors)
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_missing_parent(self):
        self.write(self.story, {"parent": "EPIC-missing"})
        self.assertIn("missing", str(self.repo.scan().errors[self.story.path]))

    def test_invalid_parent_quarantines_descendants_only(self):
        task = self.repo.create("task", "Task", parent=self.story.id)
        independent = self.repo.create("bug", "Unrelated")
        self.write(self.story, {"parent": "EPIC-missing"})
        result = self.repo.scan()
        self.assertIn(task.path, result.errors)
        self.assertEqual({self.epic.id, independent.id}, set(result.valid))

    def test_parent_cycle_and_wrong_parent_type(self):
        bug = self.repo.create("bug", "Bug")
        task = self.repo.create("task", "Task", parent=bug.id)
        self.write(bug, {"parent": task.id})
        self.assertIn("parent cycle", str(self.repo.scan().errors))
        self.write(self.story, {"parent": task.id})
        self.assertIn("invalid parent type", str(self.repo.scan().errors[self.story.path]))

    def test_negative_front_matter_fixtures(self):
        original = self.story.render()
        cases = {
            "missing delimiter": original.replace("---\n", "", 1),
            "unclosed": "---\nid: STORY-1\n",
            "duplicate key": original.replace("type: story", "type: story\ntype: story"),
            "bad YAML": "---\nx: [\n---\n",
            "custom tag": original.replace("title: A story", "title: !evil hi"),
            "scalar": "---\nhello\n---\n",
            "missing title": original.replace("title: A story\n", ""),
            "missing step": original.replace("step: captured\n", ""),
            "empty workflow": original.replace("workflow: default", "workflow: ''"),
            "non-string key": original.replace("title: A story", "123: value"),
            "alias": original.replace("title: A story", "title: &title A story\nstep: *title"),
            "unknown field": original.replace("title: A story", "title: A story\ndepends_on: []"),
            "null type": original.replace("type: story", "type: null"),
            "bad ID": original.replace("id: STORY-001", "id: ../../escape"),
            "epic with step": self.epic.render().replace("type: epic", "type: epic\nstep: captured"),
        }
        for name, fixture in cases.items():
            with self.subTest(fixture=name):
                self.story.path.write_text(fixture)
                self.assertIn(self.story.path, self.repo.scan().errors)
                self.assertEqual(fixture, self.story.path.read_text())

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

    def test_cli_capture_validate_and_nonzero_errors(self):
        prefix = ["backlog", "--workspace", str(self.root)]
        with contextlib.redirect_stdout(io.StringIO()) as output:
            main(prefix + ["capture", "bug", "CLI bug"])
            main(prefix + ["validate"])
        self.assertRegex(output.getvalue(), r"BUG-001\s+captured\s+human")
        self.story.path.write_text("broken")
        with contextlib.redirect_stdout(io.StringIO()) as output, self.assertRaises(SystemExit) as exit:
            main(prefix + ["validate"])
        self.assertEqual(1, exit.exception.code)
        self.assertIn(str(self.story.path), output.getvalue())


if __name__ == "__main__":
    unittest.main()
