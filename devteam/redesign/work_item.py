"""Work items as YAML, one file per item at backlog/<kind>s/<ID>.yaml; any field may appear on any type."""
from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator
import yaml

from devteam import git
from devteam.backlog import InvalidRecord, StrictLoader, mutation, valid_id

from . import flow
from .steps import REQUIREMENTS

DIRECTORIES = {"epic": "epics", "story": "stories", "task": "tasks", "bug": "bugs", "request": "requests"}
DEFAULT_WORKFLOW = "default"
WORKFLOWS = {"request": "request"}


class InvalidWorkItem(ValueError):
    pass


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Change(Model):
    name: str
    description: str


class Question(Model):
    question: str
    answer: str | None = None


class DroppedDraft(Model):
    id: str
    reason: str

    @field_validator("id")
    @classmethod
    def _id(cls, value):
        if not valid_id(value):
            raise ValueError("must be an item ID")
        return value


class StandardChoice(Model):
    name: str
    reason: str


class Requirements(Model):
    """What an item asks for: captured on the item, then revised by analysis and answering."""
    overview: str | None = None
    scope: str | None = None
    context: str | None = None
    change: str | None = None
    current_behaviour: str | None = None
    expected_behaviour: str | None = None
    steps_to_reproduce: list[str] | None = None
    acceptance_criteria: list[str] | None = None
    personas_affected: list[str] | None = None
    glossary_changes: list[Change] | None = None
    persona_changes: list[Change] | None = None
    standards: list[StandardChoice] | None = None
    questions: list[Question] | None = None
    work_items: list[str] | None = None  # the items a request was divided into
    dropped: list[DroppedDraft] | None = None

    @field_validator("work_items")
    @classmethod
    def _work_items(cls, value):
        if value is not None:
            if not all(valid_id(i) for i in value):
                raise ValueError("must be a list of item IDs")
            if len(set(value)) != len(value):
                raise ValueError("repeats an item ID")
        return value


class StepOutput(Model):
    """One run of a step: its outcome, what it produced, and whether the step it leads to has taken it."""
    step: str
    outcome: str
    to: str
    output: dict = {}
    passed: bool = False


class Identity(Model):
    """Who the item is, where it sits in the hierarchy and its place in a workflow."""
    id: str
    type: Literal["epic", "story", "task", "bug", "request"]
    title: str
    parent: str | None = None
    depends_on: list[str] | None = None
    workflow: str | None = None
    step: str | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, value):
        if not value.strip():
            raise ValueError("must be nonempty text")
        return value

    @field_validator("parent")
    @classmethod
    def _parent(cls, value):
        if value is not None and not valid_id(value):
            raise ValueError("must be an item ID")
        return value

    @field_validator("depends_on")
    @classmethod
    def _depends_on(cls, value):
        if value is not None:
            if not all(valid_id(d) for d in value):
                raise ValueError("must be a list of item IDs")
            if len(set(value)) != len(value):
                raise ValueError("repeats an item ID")
        return value

    @model_validator(mode="after")
    def _identity(self):
        if not valid_id(self.id) or not self.id.startswith(self.type.upper() + "-"):
            raise ValueError(f"id must be its uppercase type prefix and an identifier (e.g. {self.type.upper()}-001)")
        if (self.workflow is None) != (self.step is None):
            raise ValueError("workflow and step go together; an item has both or neither")
        return self


class WorkItem(Requirements, Identity):
    step_outputs: list[StepOutput] = []

    def pending(self, step_name):
        """The outputs addressed to the step that it has not yet taken, oldest first."""
        return [entry for entry in self.step_outputs if entry.to == step_name and not entry.passed]


# The harness sets these on capture and moves them only by recording a step's outcome.
OWNED = ("id", "type", "workflow", "step", "step_outputs")


def _problems(exc):
    return "; ".join(f"{'.'.join(str(p) for p in error['loc']) or 'item'}: {error['msg']}" for error in exc.errors())


def check_requirements(fragment):
    try:
        return Requirements.model_validate(fragment)
    except ValidationError as exc:
        raise InvalidWorkItem(_problems(exc)) from None


def merge_requirements(item, fragment):
    """Each field replaces the item's, but questions merge by their text so none is lost and answers stay."""
    data = item.model_dump(exclude_none=True)
    fields = check_requirements(fragment).model_dump(exclude_none=True)
    questions = fields.pop("questions", None)
    data.update(fields)
    if questions is not None:
        merged = {q["question"]: q for q in data.get("questions", [])}
        for question in questions:
            merged[question["question"]] = {**merged.get(question["question"], {}), **question}
        data["questions"] = list(merged.values())
    return data


def _build(data):
    try:
        return WorkItem.model_validate(data)
    except ValidationError as exc:
        raise InvalidWorkItem(_problems(exc)) from None


def parse(text):
    try:
        data = yaml.load(text, Loader=StrictLoader)
    except (yaml.YAMLError, InvalidRecord) as exc:
        raise InvalidWorkItem(f"not valid YAML: {exc}") from None
    return _build(data)


class _Dumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True

    def increase_indent(self, flow=False, indentless=False):
        # Indent lists under their key, as the examples are written.
        return super().increase_indent(flow, False)


def _text(dumper, value):
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|" if "\n" in value else None)


_Dumper.add_representer(str, _text)


def to_yaml(value):
    """Models and plain data alike, as the work-item files write them."""
    if isinstance(value, BaseModel):
        value = value.model_dump(exclude_none=True, exclude_defaults=True)
    elif isinstance(value, list):
        value = [v.model_dump(exclude_none=True, exclude_defaults=True) if isinstance(v, BaseModel) else v
                 for v in value]
    return yaml.dump(value, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=float("inf"))


def dump(item):
    return to_yaml(item)


def load(path):
    path = Path(path)
    item = parse(path.read_text(encoding="utf-8"))
    if path.stem != item.id:
        raise InvalidWorkItem(f"file name does not match id {item.id}")
    if path.parent.name != DIRECTORIES[item.type]:
        raise InvalidWorkItem(f"a {item.type} belongs in {DIRECTORIES[item.type]}/")
    return item


@dataclass
class Snapshot:
    items: dict = field(default_factory=dict)  # id -> every item that loaded
    paths: dict = field(default_factory=dict)  # id -> its file
    errors: dict = field(default_factory=dict)  # path -> diagnostics

    @property
    def valid(self):
        return {item_id: item for item_id, item in self.items.items() if self.paths[item_id] not in self.errors}

    def error(self, path, message):
        self.errors.setdefault(path, []).append(message)

    def add(self, path, item):
        self.items[item.id] = item
        self.paths[item.id] = path


def _dependency_cycle(start, items):
    pending = [(start, [start])]
    seen = set()
    while pending:
        current, chain = pending.pop()
        for dependency in items[current].depends_on or []:
            if dependency == start:
                return chain + [dependency]
            if dependency in items and dependency not in seen:
                seen.add(dependency)
                pending.append((dependency, chain + [dependency]))
    return None


def _check_links(snapshot):
    items = snapshot.items
    for item in items.values():
        parent = item.parent
        if parent is not None and parent not in items:
            snapshot.error(snapshot.paths[item.id], f"parent {parent} is missing or invalid")
        for dependency in item.depends_on or []:
            if dependency not in items:
                snapshot.error(snapshot.paths[item.id], f"dependency {dependency} is missing or invalid")
        for work_item in item.work_items or []:
            if work_item not in items:
                snapshot.error(snapshot.paths[item.id], f"work item {work_item} is missing or invalid")
        for drop in item.dropped or []:
            if drop.id not in items:
                snapshot.error(snapshot.paths[item.id], f"dropped item {drop.id} is missing or invalid")
        chain = [item.id]
        while parent in items:
            if parent in chain:
                snapshot.error(snapshot.paths[item.id], f"parent cycle: {' -> '.join(chain + [parent])}; remove a link")
                break
            chain.append(parent)
            parent = items[parent].parent
        if cycle := _dependency_cycle(item.id, items):
            snapshot.error(snapshot.paths[item.id], f"dependency cycle: {' -> '.join(cycle)}; remove a link")
    return snapshot


class Backlog:
    """The work items under one backlog root. Writes are validated, atomic, and committed when the root is a git work tree."""

    def __init__(self, root, workflows=None, guard=None, notice=print):
        self.root = Path(root).resolve()
        self._load_workflow = workflows or flow.load
        self._workflows = {}
        self.guard = guard
        self.notice = notice

    def path(self, item_id):
        kind = item_id.partition("-")[0].lower() if isinstance(item_id, str) else None
        if not valid_id(item_id) or kind not in DIRECTORIES:
            raise InvalidWorkItem(f"{item_id!r} is not a work-item ID")
        return self.root / DIRECTORIES[kind] / f"{item_id}.yaml"

    def get(self, item_id):
        path = self.path(item_id)
        try:
            return load(path)
        except FileNotFoundError:
            raise InvalidWorkItem(f"{item_id} does not exist") from None
        except (InvalidWorkItem, OSError, UnicodeError) as exc:
            raise InvalidWorkItem(f"{path}: {exc}") from None

    def workflow(self, name):
        if name not in self._workflows:
            self._workflows[name] = self._load_workflow(name)
        return self._workflows[name]

    def step(self, item):
        """The workflow step the item is at."""
        if item.workflow is None:
            raise InvalidWorkItem(f"{item.id} is not in a workflow")
        try:
            step = self.workflow(item.workflow).steps.get(item.step)
        except flow.InvalidWorkflow as exc:
            raise InvalidWorkItem(str(exc)) from None
        if step is None:
            raise InvalidWorkItem(f"{item.id} is at {item.step!r}, which workflow {item.workflow!r} does not define")
        return step

    def scan(self, *, replacement=None):
        snapshot = Snapshot()
        for directory in DIRECTORIES.values():
            for path in sorted((self.root / directory).glob("*.yaml")):
                try:
                    if not path.resolve().is_relative_to(self.root):
                        raise InvalidWorkItem("item path escapes the backlog root; remove the symlink")
                    item = load(path)
                    if replacement is not None and replacement.id == item.id:
                        item = replacement
                    if item.workflow is not None:
                        self.step(item)
                    snapshot.add(path, item)
                except (InvalidWorkItem, OSError, UnicodeError) as exc:
                    snapshot.error(path, str(exc))
        if replacement is not None and replacement.id not in snapshot.items:
            snapshot.add(self.path(replacement.id), replacement)
        return _check_links(snapshot)

    def create(self, kind, title, fields=None, *, item_id=None, workflow=None):
        """Capture an item; every kind but an epic starts at its workflow's initial step."""
        fields = dict(fields or {})
        if owned := [key for key in OWNED if key in fields]:
            raise InvalidWorkItem(f"the harness sets {', '.join(owned)}")
        if kind not in DIRECTORIES:
            raise InvalidWorkItem(f"type must be one of {', '.join(DIRECTORIES)}")
        with mutation(self.root):
            if item_id is None:
                number = 1
                while self.path(f"{kind.upper()}-{number:03d}").exists():
                    number += 1
                item_id = f"{kind.upper()}-{number:03d}"
            data = {"id": item_id, "type": kind, "title": title, **fields}
            if kind != "epic":
                workflow = workflow or WORKFLOWS.get(kind, DEFAULT_WORKFLOW)
                try:
                    data.update(workflow=workflow, step=self.workflow(workflow).initial)
                except flow.InvalidWorkflow as exc:
                    raise InvalidWorkItem(str(exc)) from None
            item = _build(data)
            if self.path(item_id).exists():
                raise InvalidWorkItem(f"{item_id} already exists")
            self._write(item, f"{item_id}: captured" + (f" at {item.step}" if item.step else ""))
            return item

    def update(self, item_id, fields):
        """Replace top-level fields; a None value removes the field."""
        if owned := [key for key in OWNED if key in fields]:
            raise InvalidWorkItem(f"the harness sets {', '.join(owned)}")
        with mutation(self.root):
            item = self.get(item_id)
            updated = _build({**item.model_dump(exclude_none=True), **fields})
            self._write(updated, f"{item_id}: updated {', '.join(fields)}")
            return updated

    def record(self, item_id, outcome, fragment=None):
        """Record the outcome of the item's current step and move the item to the step it leads to.

        The output is kept in step_outputs, addressed to that next step; the outputs this step was given are
        checked off. A step whose output is the requirements also merges them into the item.
        """
        with mutation(self.root):
            item = self.get(item_id)
            step = self.step(item)
            fragment = step.check(outcome, fragment)
            data = merge_requirements(item, fragment) if step.output == REQUIREMENTS else item.model_dump(exclude_none=True)
            target = step.outcomes[outcome].next
            for entry in data.get("step_outputs", []):
                if entry["to"] == step.name:
                    entry["passed"] = True
            data["step_outputs"] = data.get("step_outputs", []) + [
                {"step": step.name, "outcome": outcome, "to": target, "output": fragment}]
            data["step"] = target
            updated = _build(data)
            self._write(updated, f"{item_id}: {step.name} {outcome} -> {target}")
            return updated

    def _write(self, item, message):
        path = self.path(item.id)
        errors = self.scan(replacement=item).errors.get(path)
        if errors:
            raise InvalidWorkItem(f"{item.id}: " + "; ".join(errors))
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(dump(item), encoding="utf-8")
        os.replace(temporary, path)
        self._commit(message, path)

    def _commit(self, message, *paths):
        if not (self.root / ".git").exists():
            return
        try:
            if self.guard is not None:
                self.guard(self.root, self.notice, *paths)
            git.commit_all(self.root, message, *paths)
        except git.GitError as exc:
            raise InvalidWorkItem(f"could not commit the backlog: {exc}") from exc
