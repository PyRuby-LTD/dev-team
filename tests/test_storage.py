import contextlib
import io
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from devteam.backlog import Conflict, InvalidRecord, Repository, parse
from devteam.cli import main
from devteam.scheduler import Scheduler


POINTS = ("before_temp", "during_write", "before_flush", "before_file_fsync",
          "after_file_fsync", "before_replace", "after_replace",
          "before_directory_fsync", "after_directory_fsync")


def competing_writer(root, item_id, barrier, queue):
    repo = Repository(root)
    expected = repo.scan().valid[item_id]
    barrier.wait(timeout=10)
    try:
        result = repo.update(expected, body=f"writer {os.getpid()}\n", actor="concurrent-fixture")
        queue.put(("success", result.body))
    except Conflict as exc:
        queue.put(("conflict", str(exc)))


def competing_capture(root, barrier, queue):
    barrier.wait(timeout=10)
    record = Repository(root).create("bug", "Concurrent capture")
    queue.put(record.id)


def crash_writer(root, item_id, point):
    repo = Repository(root)
    expected = repo.scan().valid[item_id]
    def crash(name):
        if name == point:
            os._exit(73)
    repo.update(expected, body="Complete replacement café\r\n", fault=crash)


class StorageAcceptance(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = Repository(self.root)
        self.epic = self.repo.create("epic", "Epic")
        self.story = self.repo.create("story", "Story", "original narrative\r\n", parent=self.epic.id)

    def current(self):
        return Repository(self.root).scan().valid[self.story.id]

    def test_write_fault_matrix_old_or_complete_new(self):
        for point in POINTS:
            with self.subTest(point=point):
                source = self.current()
                old = source.path.read_bytes()
                def fail(name):
                    if name == point:
                        raise OSError("injected storage failure")
                with self.assertRaises(OSError):
                    self.repo.update(source, body=f"complete {point}\n", fault=fail)
                reopened = self.current()
                if point in POINTS[:6]:
                    self.assertEqual(old, source.path.read_bytes())
                else:
                    self.assertEqual(f"complete {point}\n", reopened.body)
                    self.assertEqual(source.source_revision + 1, reopened.source_revision)
                    self.assertEqual(source.metadata["history"], reopened.metadata["history"][:-1])
                self.assertEqual([], list(source.path.parent.glob(".backlog-*.tmp")))

    def test_process_crash_matrix_and_lock_recovery(self):
        ctx = multiprocessing.get_context("fork")
        for point in POINTS:
            with self.subTest(point=point):
                source = self.current()
                old = source.path.read_bytes()
                process = ctx.Process(target=crash_writer, args=(self.root, source.id, point))
                process.start()
                process.join(10)
                self.assertFalse(process.is_alive())
                self.assertEqual(73, process.exitcode)
                reopened = self.current()
                if point in POINTS[:6]:
                    self.assertEqual(old, source.path.read_bytes())
                else:
                    self.assertEqual("Complete replacement café\r\n", reopened.body)
                    self.assertEqual(source.source_revision + 1, reopened.source_revision)
                # A killed process releases flock; orphan temporary files are not items.
                self.assertEqual({}, self.repo.scan().errors)
                self.repo.update(reopened, changes={"title": "Recovered"})

    def test_competing_process_updates_one_success_one_conflict(self):
        ctx = multiprocessing.get_context("fork")
        barrier, queue = ctx.Barrier(2), ctx.Queue()
        processes = [ctx.Process(target=competing_writer, args=(self.root, self.story.id, barrier, queue)) for _ in range(2)]
        for process in processes:
            process.start()
        for process in processes:
            process.join(10)
            self.assertEqual(0, process.exitcode)
        results = [queue.get(timeout=5) for _ in processes]
        self.assertEqual(["conflict", "success"], sorted(result[0] for result in results))
        winner = next(body for status, body in results if status == "success")
        current = self.current()
        self.assertEqual(winner, current.body)
        self.assertEqual(2, current.source_revision)
        self.assertEqual(1, len(current.metadata["history"]))

    def test_coordinated_capture_allocates_unique_ids(self):
        ctx = multiprocessing.get_context("fork")
        barrier, queue = ctx.Barrier(2), ctx.Queue()
        processes = [ctx.Process(target=competing_capture, args=(self.root, barrier, queue)) for _ in range(2)]
        for process in processes:
            process.start()
        for process in processes:
            process.join(10)
            self.assertEqual(0, process.exitcode)
        self.assertEqual({"BUG-001", "BUG-002"}, {queue.get(timeout=5) for _ in processes})
        self.assertEqual({}, self.repo.scan().errors)

    def test_unpaused_body_and_metadata_edits_conflict_without_overwrite(self):
        for edited in ("body", "metadata", "malformed"):
            with self.subTest(edit=edited):
                source = self.current()
                original = source.path.read_bytes()
                if edited == "body":
                    raw = original.replace(b"original", b"external")  # Same-size edit.
                elif edited == "metadata":
                    raw = original.replace(b"title: Story", b"title: Other")
                else:
                    raw = b"---\nbroken: [\n---\nmanual narrative"
                source.path.write_bytes(raw)
                with self.assertRaisesRegex(Conflict, "reload and reconcile"):
                    self.repo.update(source, body="stale response")
                self.assertEqual(raw, source.path.read_bytes())
                source.path.write_bytes(original)

    def test_final_digest_check_detects_edit_during_temp_write(self):
        source = self.current()
        edited = source.path.read_bytes().replace(b"original", b"external")
        def edit(point):
            if point == "before_replace":
                source.path.write_bytes(edited)
        with self.assertRaises(Conflict):
            self.repo.update(source, body="managed replacement", fault=edit)
        self.assertEqual(edited, source.path.read_bytes())

    def test_actual_replace_and_fsync_errors_preserve_atomic_document(self):
        source = self.current()
        old = source.path.read_bytes()
        for syscall in ("replace", "fsync"):
            with self.subTest(syscall=syscall), patch("devteam.storage.os." + syscall, side_effect=OSError("filesystem failure")):
                with self.assertRaises(OSError):
                    self.repo.update(source, body="new version")
            self.assertEqual(old, source.path.read_bytes())
        real_fsync = os.fsync
        calls = 0
        def directory_failure(fd):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("directory fsync failed after publication")
            real_fsync(fd)
        with patch("devteam.storage.os.fsync", side_effect=directory_failure), self.assertRaises(OSError):
            self.repo.update(source, body="complete committed document")
        self.assertEqual("complete committed document", self.current().body)
        with self.assertRaises(Conflict):
            self.repo.update(source, body="blind retry")

    def test_malformed_storage_fields_are_visible_diagnostics(self):
        original = self.story.path.read_bytes()
        for fragment in ("execution:\n  status: []", "revision: true", "revision: -1", "history: false",
                         "manual_edit: {}", "execution:\n  status: pending\n  dispatch: []"):
            with self.subTest(fragment=fragment):
                text = original.decode()
                start = text.index("revision:")
                end = text.index("---\n", start)
                self.story.path.write_text(text[:start] + fragment + "\n" + text[end:])
                self.assertIn(self.story.path, self.repo.scan().errors)
        self.story.path.write_bytes(original)

    def test_pause_manual_import_restart_and_stale_response_invalidation(self):
        source = self.repo.update(self.story, changes={"x-note": {"tags": ["keep"]}, "execution": {
            "status": "running", "dispatch": {"id": "dispatch-1", "expected_revision": self.story.source_revision,
                                               "expected_file_digest": self.story.digest}}})
        paused = self.repo.pause(source)
        with self.assertRaisesRegex(Conflict, "paused"):
            Repository(self.root).update(paused, body="forbidden managed write")
        edited = parse(paused.path, paused.path.read_bytes().decode())
        edited.metadata["title"] = "Manual title"
        edited.body = "manual café\r\n"
        edited.path.write_bytes(edited.render().encode())
        current = self.current()
        self.assertEqual(paused.source_revision, current.source_revision)
        resumed = Repository(self.root).resume(current.id, expected_revision=current.source_revision, expected_digest=current.digest)
        self.assertEqual(current.source_revision + 1, resumed.source_revision)
        self.assertEqual("Manual title", resumed.metadata["title"])
        self.assertEqual("manual café\r\n", resumed.body)
        self.assertEqual({"tags": ["keep"]}, resumed.metadata["x-note"])
        self.assertNotIn("manual_edit", resumed.metadata)
        self.assertEqual({"status": "idle"}, resumed.metadata["execution"])
        self.assertEqual("manual-import", resumed.metadata["history"][-1]["event"])
        self.assertEqual("dispatch-1", resumed.metadata["history"][-1]["invalidated_dispatch"])
        for obsolete in (source, paused, current):
            with self.assertRaises(Conflict):
                self.repo.update(obsolete, body="old response")

    def test_malformed_manual_edit_remains_visible_and_untouched(self):
        paused = self.repo.pause(self.story)
        malformed = b"---\nbroken: [\n---\nmanually edited"
        paused.path.write_bytes(malformed)
        with self.assertRaises(InvalidRecord):
            self.repo.resume(paused.id, expected_revision=paused.source_revision, expected_digest=paused.digest)
        scan = Scheduler(Repository(self.root)).scan()
        self.assertIn(paused.path, scan.snapshot.errors)
        self.assertIn(paused.path, scan.blocked)
        self.assertEqual(malformed, paused.path.read_bytes())

    def test_resume_protects_history_and_rejects_stale_digest(self):
        paused = self.repo.pause(self.story)
        original = paused.path.read_bytes()
        edited = parse(paused.path, original.decode())
        edited.metadata["history"][0]["actor"] = "rewritten"
        edited.path.write_bytes(edited.render().encode())
        current = self.current()
        with self.assertRaisesRegex(InvalidRecord, "protected"):
            self.repo.resume(current.id, expected_revision=current.source_revision, expected_digest=current.digest)
        edited.path.write_bytes(original + b"manual text")
        with self.assertRaises(Conflict):
            self.repo.resume(paused.id, expected_revision=paused.source_revision, expected_digest=paused.digest)

    def test_persisted_failure_and_evidence_do_not_advance_workflow(self):
        failed = self.repo.update(self.story, changes={"execution": {"status": "failed", "error": "engine exited 2",
                                "evidence": ["../evidence/failure.txt"]}}, evidence=["../evidence/failure.txt"])
        # Contradictory secondary file is ignored even after a fresh repository starts.
        (self.root / "state.json").write_text('{"state":"implemented","execution":"idle"}')
        reopened = self.current()
        self.assertEqual("proposed", reopened.metadata["state"])
        self.assertEqual("failed", reopened.metadata["execution"]["status"])
        self.assertEqual(failed.metadata, reopened.metadata)
        self.assertEqual(["../evidence/failure.txt"], reopened.metadata["history"][-1]["evidence"])
        self.assertFalse(Scheduler(Repository(self.root)).scan().eligible)

    def test_rejected_updates_preserve_all_bytes(self):
        source = self.repo.update(self.story, changes={"x-unrelated": {"value": [1, 2]}})
        before = source.path.read_bytes()
        for changes in ({"title": ""}, {"execution": {"status": "done"}}, {"revision": 99},
                        {"parent": "EPIC-missing"}, {"depends_on": [source.id]}, {"id": "STORY-renamed"},
                        {"execution": {"status": "failed", "evidence": "bad"}}):
            with self.subTest(changes=changes), self.assertRaises(InvalidRecord):
                self.repo.update(source, changes=changes)
            self.assertEqual(before, source.path.read_bytes())

    def test_legacy_revision_zero_is_upgraded_without_changing_narrative(self):
        data = dict(self.story.metadata)
        for key in ("revision", "execution", "history"):
            data.pop(key)
        self.story.metadata = data
        self.story.path.write_bytes(self.story.render().encode())
        source = self.current()
        self.assertEqual(0, source.source_revision)
        result = self.repo.update(source, changes={"title": "Upgraded"})
        self.assertEqual(1, result.source_revision)
        self.assertEqual(source.body, result.body)

    def test_cli_pause_resume_update_and_conflict(self):
        prefix = ["backlog", "--workspace", str(self.root)]
        def command(action, record, extra=()):
            with contextlib.redirect_stdout(io.StringIO()):
                main(prefix + [action, record.id, "--revision", str(record.source_revision), "--digest", record.digest] + list(extra))
        command("pause", self.story)
        command("resume", self.current())
        command("update", self.current(), ["--title", "CLI updated"])
        self.assertEqual("CLI updated", self.current().metadata["title"])
        with self.assertRaises(SystemExit):
            command("update", self.story, ["--title", "Stale"])


if __name__ == "__main__":
    unittest.main()
