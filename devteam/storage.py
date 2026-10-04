"""Local POSIX storage: advisory managed-writer lock and single-file commits."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import hashlib
import os
import tempfile
import uuid

from .backlog import Conflict, InvalidRecord, Record, parse


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _integer(value):
    return type(value) is int and value >= 0


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _evidence(value):
    return isinstance(value, list) and all(_text(ref) for ref in value)


def validate_storage(data):
    if "revision" in data and not _integer(data["revision"]):
        raise InvalidRecord("revision must be a nonnegative integer")
    if "execution" in data:
        execution = data["execution"]
        if not isinstance(execution, dict) or set(execution) - {"status", "error", "evidence", "dispatch"}:
            raise InvalidRecord("execution must contain status and optional error/evidence/dispatch")
        if not _text(execution.get("status")) or execution["status"] not in {"idle", "pending", "running", "waiting-human", "failed", "uncertain"}:
            raise InvalidRecord("invalid execution status; workflow progress belongs in state")
        if "error" in execution and not _text(execution["error"]):
            raise InvalidRecord("execution error must be nonempty text")
        if "evidence" in execution and not _evidence(execution["evidence"]):
            raise InvalidRecord("execution evidence must be a list of references")
        if "dispatch" in execution:
            dispatch = execution["dispatch"]
            if (not isinstance(dispatch, dict) or set(dispatch) != {"id", "expected_revision", "expected_file_digest"}
                    or not _text(dispatch["id"]) or not _integer(dispatch["expected_revision"])
                    or not _digest(dispatch["expected_file_digest"])):
                raise InvalidRecord("dispatch requires id, expected_revision and expected_file_digest")
    if "history" in data:
        history = data["history"]
        if not isinstance(history, list):
            raise InvalidRecord("history must be a list")
        ids = set()
        for entry in history:
            required = {"id", "actor", "at", "event", "before_revision", "after_revision", "before_state", "after_state", "source_digest", "evidence"}
            if not isinstance(entry, dict) or set(entry) - (required | {"invalidated_dispatch"}) or required - set(entry):
                raise InvalidRecord("history entry has missing or unknown fields")
            if any(not _text(entry[key]) for key in ("id", "actor", "at", "event", "before_state", "after_state")):
                raise InvalidRecord("history identity, actor, timestamp, event and states must be text")
            if (not _integer(entry["before_revision"]) or not _integer(entry["after_revision"])
                    or entry["after_revision"] != entry["before_revision"] + 1
                    or entry["after_revision"] > data.get("revision", 0)
                    or not _digest(entry["source_digest"]) or not _evidence(entry["evidence"])):
                raise InvalidRecord("invalid history revisions, source digest or evidence")
            if entry["id"] in ids:
                raise InvalidRecord("duplicate history event ID")
            ids.add(entry["id"])
            if "invalidated_dispatch" in entry and not _text(entry["invalidated_dispatch"]):
                raise InvalidRecord("invalidated_dispatch must be text")
    if "manual_edit" in data:
        pause = data["manual_edit"]
        if (not isinstance(pause, dict) or set(pause) != {"paused_revision", "baseline_digest", "protected_digest"}
                or not _integer(pause["paused_revision"]) or pause["paused_revision"] != data.get("revision")
                or not _digest(pause["baseline_digest"]) or not _digest(pause["protected_digest"])):
            raise InvalidRecord("manual_edit requires the current paused_revision and baseline_digest")


@contextmanager
def mutation_lock(root):
    root.mkdir(parents=True, exist_ok=True)
    # Never unlink the lock: all processes must continue to lock the same inode.
    flags = os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW
    fd = os.open(root / ".backlog.lock", flags, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def atomic_write(path, raw, *, create=False, check=None, fault=None):
    def checkpoint(name):
        if fault:
            fault(name)
    checkpoint("before_temp")
    mode = None if create else path.stat().st_mode & 0o777
    fd, name = tempfile.mkstemp(prefix=".backlog-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            if mode is not None:
                os.fchmod(stream.fileno(), mode)
            midpoint = len(raw) // 2
            stream.write(raw[:midpoint])
            checkpoint("during_write")
            stream.write(raw[midpoint:])
            checkpoint("before_flush")
            stream.flush()
            checkpoint("before_file_fsync")
            os.fsync(stream.fileno())
        checkpoint("after_file_fsync")
        checkpoint("before_replace")
        if check:
            check()
        if create:
            # Hard-link publishes a complete file without overwriting a destination.
            os.link(name, path)
        else:
            os.replace(name, path)
        checkpoint("after_replace")
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            checkpoint("before_directory_fsync")
            os.fsync(directory)
            checkpoint("after_directory_fsync")
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _path(repo, path):
    path = path.absolute()
    if path.is_symlink() or not path.resolve().is_relative_to(repo.root):
        raise InvalidRecord("item path escapes backlog root or is a symlink")
    if path.relative_to(repo.root).parts[0] not in {"epics", "stories", "tasks", "bugs"}:
        raise InvalidRecord("item must be in a backlog item directory")
    return path


def _conflict():
    return Conflict("revision/content conflict; reload and reconcile the current Markdown. "
                    "For manual edits use pause, edit, validate, then resume; no silent merge was applied")


def _check(path, revision, expected_digest):
    raw = path.read_bytes()
    if digest(raw) != expected_digest:
        raise _conflict()
    record = parse(path, raw.decode("utf-8"))
    if record.source_revision != revision:
        raise _conflict()
    return record


def _baseline(record):
    metadata = deepcopy(record.metadata)
    metadata.pop("manual_edit", None)
    return digest(Record(record.path, metadata, record.body).render().encode("utf-8"))


def _protected(record):
    import yaml
    keys = ("schema_version", "id", "type", "revision", "history", "execution", "state", "authorisation")
    return digest(yaml.safe_dump({key: record.metadata.get(key) for key in keys}, sort_keys=True).encode("utf-8"))


def _finish(repo, current, candidate, actor, evidence, event, fault=None, invalidated=None):
    if not _text(actor):
        raise InvalidRecord("actor must be nonempty text")
    revision = current.source_revision
    candidate.metadata["revision"] = revision + 1
    entry = dict(id=str(uuid.uuid4()), actor=actor, at=datetime.now(timezone.utc).isoformat(),
                 event=event, before_revision=revision, after_revision=revision + 1,
                 before_state=current.metadata["state"], after_state=candidate.metadata["state"],
                 source_digest=current.digest, evidence=list(evidence))
    if invalidated:
        entry["invalidated_dispatch"] = invalidated
    candidate.metadata.setdefault("history", []).append(entry)
    if event == "pause":
        candidate.metadata["manual_edit"] = {"paused_revision": revision + 1,
                                             "baseline_digest": _baseline(candidate),
                                             "protected_digest": _protected(candidate)}
    raw = candidate.render().encode("utf-8")
    validated = parse(candidate.path, raw.decode("utf-8"))
    snapshot = repo.scan(replacement=validated)
    if snapshot.errors:
        raise InvalidRecord("repair backlog errors before committing: " + str(snapshot.errors))
    atomic_write(candidate.path, raw, check=lambda: _check(candidate.path, revision, current.digest), fault=fault)
    return validated


def commit(repo, expected, *, changes=None, body=None, actor="local-operator", evidence=(), mode="update", fault=None):
    with mutation_lock(repo.root):
        path = _path(repo, expected.path)
        current = _check(path, expected.source_revision, expected.digest)
        if "manual_edit" in current.metadata:
            raise Conflict("item is paused for manual editing; validate and resume before managed updates")
        changes = deepcopy(changes or {})
        if set(changes) & {"id", "type", "schema_version", "revision", "history", "manual_edit"}:
            raise InvalidRecord("identity, revision, history and pause bookkeeping are protected")
        candidate = Record(path, deepcopy(current.metadata), current.body if body is None else body)
        candidate.metadata.update(changes)
        return _finish(repo, current, candidate, actor, evidence, mode, fault)


def resume(repo, item_id, revision, expected_digest, actor):
    with mutation_lock(repo.root):
        snapshot = repo.scan()
        matches = [r for r in snapshot.records.values() if r.id == item_id]
        if len(matches) != 1:
            raise InvalidRecord("resume requires one valid local record; repair malformed Markdown first: " + str(snapshot.errors))
        current = _check(_path(repo, matches[0].path), revision, expected_digest)
        pause = current.metadata.get("manual_edit")
        if not pause:
            raise InvalidRecord("item is not paused")
        if _protected(current) != pause["protected_digest"]:
            raise InvalidRecord("manual edit changed protected identity, progress, permission or execution/history; restore those fields before resume")
        candidate = Record(current.path, deepcopy(current.metadata), current.body)
        changed = _baseline(current) != pause["baseline_digest"]
        candidate.metadata.pop("manual_edit")
        invalidated = None
        if changed:
            execution = candidate.metadata.setdefault("execution", {"status": "idle"})
            dispatch = execution.pop("dispatch", None)
            invalidated = dispatch["id"] if dispatch else None
            if dispatch or execution["status"] in {"pending", "running", "waiting-human"}:
                execution["status"] = "idle"
        return _finish(repo, current, candidate, actor, (), "manual-import" if changed else "resume", invalidated=invalidated)
