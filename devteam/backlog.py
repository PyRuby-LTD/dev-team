"""Markdown work items. Front matter holds identity, hierarchy and the current workflow step."""
from dataclasses import dataclass, field
from pathlib import Path
import os
import re

import yaml

from . import git
from . import workflow as workflows


class InvalidRecord(ValueError):
    pass


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
FIELDS = {"id", "type", "title", "parent", "workflow", "step"}
PARENTS = {"story": {"epic"}, "task": {"story", "bug"}, "bug": {"epic", "story", "task"}}
ID = re.compile(r"[A-Z][A-Z0-9]*-[A-Za-z0-9][A-Za-z0-9_-]*\Z")

DEFAULT_WORKFLOW = "default"


def valid_id(value):
    return isinstance(value, str) and ID.fullmatch(value) is not None


def validate_metadata(data):
    if not isinstance(data, dict):
        raise InvalidRecord("front matter must be a mapping")
    for key in data:
        if key not in FIELDS:
            raise InvalidRecord(f"unknown field {key!r}; allowed: {', '.join(sorted(FIELDS))}")
    missing = {"id", "type", "title"} - data.keys()
    if missing:
        raise InvalidRecord(f"missing required fields: {', '.join(sorted(missing))}")
    for key in ("type", "title"):
        if not isinstance(data[key], str) or not data[key].strip():
            raise InvalidRecord(f"{key} must be a nonempty string")
    if data["type"] not in TYPES:
        raise InvalidRecord("type must be epic, story, task or bug")
    if not valid_id(data["id"]) or not data["id"].startswith(data["type"].upper() + "-"):
        raise InvalidRecord("id must use its uppercase type prefix and a nonempty identifier (e.g. STORY-001)")
    parent = data.get("parent")
    if parent is not None and not valid_id(parent):
        raise InvalidRecord("parent must be null or an item ID")
    if data["type"] == "epic":
        # Epics group work; only their children move through a workflow.
        extra = {"parent", "workflow", "step"} & {k for k, v in data.items() if v is not None}
        if extra:
            raise InvalidRecord(f"epics must have no {', '.join(sorted(extra))}")
        return
    if data["type"] in {"story", "task"} and parent is None:
        raise InvalidRecord(f"{data['type']} requires a parent")
    for key in ("workflow", "step"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise InvalidRecord(f"{key} must be a nonempty string")


def parse(path, text):
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise InvalidRecord("missing opening front-matter delimiter --- on line 1")
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip("\r\n") == "---"), None)
    if end is None:
        raise InvalidRecord("missing closing front-matter delimiter ---")
    try:
        source = "".join(lines[1:end])
        for token in yaml.scan(source):
            if isinstance(token, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken)):
                raise InvalidRecord("YAML aliases and anchors are unsupported; use explicit values")
        data = yaml.load(source, Loader=StrictLoader)
    except yaml.YAMLError as exc:
        raise InvalidRecord(f"malformed or unsupported YAML: {exc}") from exc
    validate_metadata(data)
    return Record(Path(path), data, "".join(lines[end + 1:]))


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
        if parent is None:
            continue
        if parent not in unique:
            result.error(record.path, f"parent {parent} is missing, invalid or ambiguous; repair its record")
        elif unique[parent].metadata["type"] not in PARENTS[record.metadata["type"]]:
            result.error(record.path, f"invalid parent type for {record.metadata['type']}: {parent}")
        chain = [record.id]
        while parent in unique:
            chain.append(parent)
            if parent in chain[:-1]:
                result.error(record.path, f"parent cycle: {' -> '.join(chain)}; remove a link")
                break
            parent = unique[parent].metadata.get("parent")
    # An invalid parent quarantines its descendants, not unrelated work.
    changed = True
    while changed:
        changed = False
        for record in unique.values():
            parent = record.metadata.get("parent")
            if record.path not in result.errors and parent in unique and unique[parent].path in result.errors:
                result.error(record.path, f"parent {parent} has validation errors; repair it first")
                changed = True
    return result


class Repository:
    """Explicit backlog root; only epics/stories/tasks/bugs directories contain items."""
    def __init__(self, root, workflows=None, roles=None):
        self.root = Path(root).resolve()
        self.workflow_dir = workflows
        self.roles = roles
        self._workflows = {}

    def workflow(self, name):
        if name not in self._workflows:
            self._workflows[name] = workflows.load(name, self.workflow_dir, self.roles)
        return self._workflows[name]

    def commit(self, message):
        # Only a backlog that is its own git working tree is versioned by the harness.
        if (self.root / ".git").exists():
            try:
                git.commit_all(self.root, message)
            except git.GitError as exc:
                raise InvalidRecord(f"could not commit the backlog: {exc}") from exc

    def step(self, record):
        """The workflow step a record is at; raises if either is undefined."""
        definition = self.workflow(record.metadata["workflow"])
        step = definition.steps.get(record.metadata["step"])
        if step is None:
            raise InvalidRecord(f"step {record.metadata['step']!r} is not defined in workflow {definition.name!r}")
        return step

    def scan(self):
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
                    record = parse(path, path.read_bytes().decode("utf-8"))
                    if record.metadata["type"] != kind:
                        raise InvalidRecord(f"type does not match directory {directory.name}")
                    if kind != "epic":
                        self.step(record)
                    result.records[path] = record
                except (InvalidRecord, workflows.InvalidWorkflow, OSError, UnicodeError) as exc:
                    result.error(path, str(exc))
        return validate_links(result)

    def create(self, kind, title, body="", *, parent=None, item_id=None):
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
        metadata = dict(id=item_id, type=kind, title=title)
        if parent is not None:
            metadata["parent"] = parent
        if kind != "epic":
            metadata.update(workflow=DEFAULT_WORKFLOW, step=self.workflow(DEFAULT_WORKFLOW).initial)
        validate_metadata(metadata)
        if item_id in used:
            raise InvalidRecord(f"duplicate ID {item_id}; choose a unique ID")
        record = Record(self.root / DIRECTORIES[kind] / (item_id + ".md"), metadata, body)
        snapshot.records[record.path] = record
        validate_links(snapshot)
        if snapshot.errors:
            raise InvalidRecord(str(snapshot.errors))
        record.path.parent.mkdir(parents=True, exist_ok=True)
        with record.path.open("xb") as fh:
            fh.write(record.render().encode("utf-8"))
        self.commit(f"{item_id}: captured" + (f" at {metadata['step']}" if kind != "epic" else ""))
        return record

    def transition(self, item_id, name):
        record = self.scan().valid.get(item_id)
        if record is None:
            raise InvalidRecord(f"{item_id} is missing or invalid; run validate")
        if record.metadata["type"] == "epic":
            raise InvalidRecord("epics have no workflow step")
        step = self.step(record)
        if name not in step.transitions:
            valid = ", ".join(step.transitions) or "none (terminal step)"
            raise InvalidRecord(f"{name!r} is not a transition from {step.name!r}; valid: {valid}")
        target = step.transitions[name]
        # Rewrite only the step line so the rest of the file stays byte for byte.
        lines = record.path.read_bytes().decode("utf-8").splitlines(keepends=True)
        end = next(i for i in range(1, len(lines)) if lines[i].rstrip("\r\n") == "---")
        for i in range(1, end):
            if re.match(r"step\s*:", lines[i]):
                ending = lines[i][len(lines[i].rstrip("\r\n")):]
                lines[i] = "step: " + yaml.safe_dump(target).splitlines()[0] + ending
        text = "".join(lines)
        updated = parse(record.path, text)
        if updated.metadata["step"] != target or updated.body != record.body:
            raise InvalidRecord(f"could not rewrite the step line in {record.path}")
        temporary = record.path.with_name(record.path.name + ".tmp")
        temporary.write_bytes(text.encode("utf-8"))
        os.replace(temporary, record.path)
        self.commit(f"{item_id}: {name} -> {target}")
        return updated
