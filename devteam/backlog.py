"""Version-one planning records. No runtime enrollment or dispatch authority."""
from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import re

import yaml


class InvalidRecord(ValueError):
    pass


class Conflict(InvalidRecord):
    """The source changed; reload and reconcile rather than silently merging."""


class StrictLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise InvalidRecord("mapping keys must be strings")
            if key in result:
                raise InvalidRecord(f"duplicate key {key!r}; keep one value")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


@dataclass
class Record:
    path: Path
    metadata: dict
    body: str
    digest: str | None = None
    source_revision: int = 0

    @property
    def id(self):
        return self.metadata["id"]

    def render(self):
        validate_metadata(self.metadata)
        if not isinstance(self.body, str):
            raise InvalidRecord("narrative body must be text")
        return "---\n" + yaml.safe_dump(self.metadata, sort_keys=False, allow_unicode=True) + "---\n" + self.body


TYPES = {"epic", "story", "task", "bug"}
DIRECTORIES = {"epic": "epics", "story": "stories", "task": "tasks", "bug": "bugs"}
REQUIRED = {"schema_version", "id", "type", "title", "state", "authorisation", "depends_on"}
OPTIONAL = {"parent", "owner", "detail", "revision", "execution", "history", "manual_edit"}
ID = re.compile(r"[A-Z][A-Z0-9]*-[A-Za-z0-9][A-Za-z0-9_-]*\Z")


def valid_id(value):
    return isinstance(value, str) and ID.fullmatch(value) is not None


def validate_metadata(data):
    if not isinstance(data, dict):
        raise InvalidRecord("front matter must be a mapping")
    missing = REQUIRED - data.keys()
    if missing:
        raise InvalidRecord(f"missing required fields: {', '.join(sorted(missing))}")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise InvalidRecord("unsupported schema_version; expected integer 1")
    for key in data:
        if not isinstance(key, str) or (key not in REQUIRED | OPTIONAL and not key.startswith("x-")):
            raise InvalidRecord(f"unknown field {key!r}; runtime fields require a future schema")
    for key in ("type", "title", "state", "authorisation"):
        if not isinstance(data[key], str) or not data[key].strip():
            raise InvalidRecord(f"{key} must be a nonempty string")
    if data["type"] not in TYPES:
        raise InvalidRecord("type must be epic, story, task or bug")
    if not valid_id(data["id"]) or not data["id"].startswith(data["type"].upper() + "-"):
        raise InvalidRecord("id must use its uppercase type prefix and a nonempty identifier (e.g. STORY-001)")
    if data["state"] not in {"proposed", "in-progress", "implemented"}:
        raise InvalidRecord("planning state must be proposed, in-progress or implemented; runtime states are unsupported")
    if data["authorisation"] not in {"not-played", "played"}:
        raise InvalidRecord("authorisation must be not-played or played")
    parent = data.get("parent")
    if parent is not None and not valid_id(parent):
        raise InvalidRecord("parent must be null or an item ID")
    if data["type"] == "epic" and parent is not None:
        raise InvalidRecord("epics must have no parent")
    if data["type"] in {"story", "task"} and parent is None:
        raise InvalidRecord(f"{data['type']} requires a parent")
    deps = data["depends_on"]
    if not isinstance(deps, list) or not all(valid_id(dep) for dep in deps):
        raise InvalidRecord("depends_on must be a list of item IDs")
    if len(set(deps)) != len(deps):
        raise InvalidRecord("depends_on contains repeated IDs")
    if "owner" in data and (not isinstance(data["owner"], str) or not data["owner"].strip()):
        raise InvalidRecord("owner must be a nonempty planning attribution")
    if "detail" in data and (data["type"] != "epic" or data["detail"] not in ("detailed", "deferred")):
        raise InvalidRecord("detail is only allowed for epics, as detailed or deferred")
    from .storage import validate_storage
    validate_storage(data)


def parse(path, text):
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise InvalidRecord("missing opening front-matter delimiter --- on line 1")
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip("\r\n") == "---"), None)
    if end is None:
        raise InvalidRecord("missing closing front-matter delimiter ---")
    try:
        source = "".join(lines[1:end])
        # Aliases/anchors and merge keys complicate authority; disallow them.
        for token in yaml.scan(source):
            if isinstance(token, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken)):
                raise InvalidRecord("YAML aliases and anchors are unsupported; use explicit values")
        data = yaml.load(source, Loader=StrictLoader)
    except yaml.YAMLError as exc:
        raise InvalidRecord(f"malformed or unsupported YAML: {exc}") from exc
    validate_metadata(data)
    return Record(Path(path), data, "".join(lines[end + 1:]),
                  hashlib.sha256(text.encode("utf-8")).hexdigest(), data.get("revision", 0))


@dataclass
class Snapshot:
    records: dict = field(default_factory=dict)  # path -> locally valid record
    errors: dict = field(default_factory=dict)  # path -> diagnostics

    @property
    def valid(self):
        return {r.id: r for p, r in self.records.items() if p not in self.errors}

    def error(self, path, message):
        self.errors.setdefault(path, []).append(message)


def validate_links(result):
    by_id = {}
    for record in result.records.values():
        by_id.setdefault(record.id, []).append(record)
    for item_id, records in by_id.items():
        if len(records) > 1:
            for record in records:
                result.error(record.path, f"duplicate ID {item_id}: " + ", ".join(str(r.path) for r in records))
    unique = {key: records[0] for key, records in by_id.items() if len(records) == 1}
    for record in unique.values():
        parent = record.metadata.get("parent")
        for target in ([parent] if parent else []) + record.metadata["depends_on"]:
            if target not in unique:
                result.error(record.path, f"reference {target} is missing, invalid or ambiguous; repair its record")
        if parent in unique:
            allowed = {"story": {"epic"}, "task": {"story", "bug"}, "bug": {"epic", "story", "task"}}
            if unique[parent].metadata["type"] not in allowed.get(record.metadata["type"], set()):
                result.error(record.path, f"invalid parent type for {record.metadata['type']}: {parent}")
    # Iterative traversal avoids recursion limits on long dependency chains.
    for relation in ("parent", "depends_on"):
        graph = {key: ([r.metadata["parent"]] if r.metadata.get("parent") else [])
                 if relation == "parent" else r.metadata["depends_on"] for key, r in unique.items()}
        done = set()
        for start in graph:
            stack = [(start, False)]
            active = []
            positions = {}
            while stack:
                key, leaving = stack.pop()
                if leaving:
                    active.pop()
                    positions.pop(key)
                    done.add(key)
                elif key in positions:
                    cycle = active[positions[key]:] + [key]
                    for member in cycle[:-1]:
                        result.error(unique[member].path, f"{relation} cycle: {' -> '.join(cycle)}; remove a link")
                elif key in graph and key not in done:
                    positions[key] = len(active)
                    active.append(key)
                    stack.append((key, True))
                    stack.extend((target, False) for target in reversed(graph[key]))
    # Invalid prerequisites/ancestors quarantine their dependants, not unrelated work.
    changed = True
    while changed:
        changed = False
        for record in unique.values():
            if record.path in result.errors:
                continue
            refs = record.metadata["depends_on"] + ([record.metadata["parent"]] if record.metadata.get("parent") else [])
            for target in refs:
                if target in unique and unique[target].path in result.errors:
                    result.error(record.path, f"reference {target} has validation errors; repair it first")
                    changed = True
                    break
    return result


class Repository:
    """Explicit backlog root; only epics/stories/tasks/bugs directories contain items."""
    def __init__(self, root):
        self.root = Path(root).resolve()

    def scan(self, replacement=None):
        result = Snapshot()
        for kind in sorted(TYPES):
            directory = self.root / DIRECTORIES[kind]
            if not directory.resolve().is_relative_to(self.root):
                result.error(directory, "item directory escapes backlog root; remove symlink")
                continue
            for path in sorted(directory.rglob("*.md")):
                try:
                    if not path.resolve().is_relative_to(self.root):
                        raise InvalidRecord("item path escapes backlog root; remove symlink")
                    record = replacement if replacement is not None and path == replacement.path else parse(path, path.read_bytes().decode("utf-8"))
                    if record.metadata["type"] != kind:
                        raise InvalidRecord(f"type does not match directory {directory.name}")
                    result.records[path] = record
                except (InvalidRecord, OSError, UnicodeError) as exc:
                    result.error(path, str(exc))
        return validate_links(result)

    def create(self, kind, title, body="", *, parent=None, depends_on=(), item_id=None):
        from .storage import mutation_lock
        with mutation_lock(self.root):
            return self._create(kind, title, body, parent=parent, depends_on=depends_on, item_id=item_id)

    def _create(self, kind, title, body="", *, parent=None, depends_on=(), item_id=None):
        if kind not in TYPES:
            raise InvalidRecord("type must be epic, story, task or bug")
        snapshot = self.scan()
        if snapshot.errors:
            raise InvalidRecord("repair backlog errors before capture: " + str(snapshot.errors))
        used = {r.id for r in snapshot.records.values()}
        if item_id is None:
            number = 1
            while f"{kind.upper()}-{number:03d}" in used:
                number += 1
            item_id = f"{kind.upper()}-{number:03d}"
        metadata = dict(schema_version=1, id=item_id, type=kind, title=title,
                        state="proposed", authorisation="not-played", depends_on=list(depends_on),
                        revision=1, execution={"status": "idle"}, history=[])
        if parent is not None:
            metadata["parent"] = parent
        validate_metadata(metadata)
        path = self.root / DIRECTORIES[kind] / (item_id + ".md")
        if path in snapshot.records or item_id in used:
            raise InvalidRecord(f"duplicate ID {item_id}; choose a unique ID")
        record = Record(path, metadata, body)
        snapshot.records[path] = record
        validate_links(snapshot)
        if snapshot.errors:
            raise InvalidRecord(str(snapshot.errors))
        path.parent.mkdir(parents=True, exist_ok=True)
        from .storage import atomic_write
        atomic_write(path, record.render().encode("utf-8"), create=True)
        return parse(path, path.read_bytes().decode("utf-8"))

    def update(self, expected, *, changes=None, body=None, actor="local-operator", evidence=(), fault=None):
        from .storage import commit
        return commit(self, expected, changes=changes, body=body, actor=actor, evidence=evidence, fault=fault)

    def pause(self, expected, *, actor="local-operator"):
        from .storage import commit
        return commit(self, expected, actor=actor, mode="pause")

    def resume(self, item_id, *, expected_revision, expected_digest, actor="local-operator"):
        from .storage import resume
        return resume(self, item_id, expected_revision, expected_digest, actor)
