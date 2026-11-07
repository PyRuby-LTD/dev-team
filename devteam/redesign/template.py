"""Jinja2 templates: agent prompts from prompts/ and the TUI's detail view from views/, each rendered with the work item, its pending input and its standards."""
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError
import yaml

from devteam.config import ROOT, harness_command

from .steps import AgentStep
from .work_item import Requirements, to_yaml

RUN_VALUES = ("checkout", "branch", "base", "verify_log", "conflicted_files", "evidence_dir")
SUBMIT = "_submit.md"
DETAIL = "detail.md"


class InvalidTemplate(ValueError):
    pass


@dataclass(frozen=True)
class Standard:
    name: str
    kind: str
    description: str
    body: str


def load_standards(directory=None):
    standards = {}
    for path in sorted(Path(directory or ROOT / "standards").glob("*.md")):
        _, front, body = path.read_text(encoding="utf-8").split("---\n", 2)
        meta = yaml.safe_load(front)
        standards[meta["name"]] = Standard(meta["name"], meta["kind"], meta["description"], body.strip())
    return standards


def chosen_standards(item, available):
    names = [choice.name for choice in item.standards or []]
    unknown = [name for name in names if name not in available]
    if unknown:
        raise InvalidTemplate(f"{item.id} names standards that do not exist: {', '.join(unknown)}")
    return [available[name] for name in names]


def _environment(directory):
    environment = Environment(loader=FileSystemLoader(directory), undefined=StrictUndefined, trim_blocks=True,
                              lstrip_blocks=True, keep_trailing_newline=True, autoescape=False)
    environment.filters["yaml"] = to_yaml
    return environment


class Templates:
    def __init__(self, directory=None, standards=None, views=None):
        self.directory = Path(directory or ROOT / "prompts").resolve()
        self.standards = load_standards(standards)
        self.environment = _environment(self.directory)
        self.views = _environment(Path(views or ROOT / "views").resolve())

    def context(self, item, step, values=None, backlog=None):
        return {
            "item": item,
            "step": step,
            "workflow": backlog.workflow(item.workflow) if backlog and item.workflow else None,
            "pending": item.pending(step.name) if step else [],
            "work_items": [backlog.get(i) for i in item.work_items or []] if backlog else [],
            "requirements": Requirements.model_validate(item.model_dump(include=set(Requirements.model_fields))),
            "standards": chosen_standards(item, self.standards),
            "available_standards": list(self.standards.values()),
            "requirement_fields": list(Requirements.model_fields),
            "harness_command": harness_command(),
            **(values or {}),
        }

    def prompt(self, item, step, values=None, backlog=None):
        """The step's prompt followed by the instructions for submitting its outcome."""
        if not isinstance(step, AgentStep):
            raise InvalidTemplate(f"step {step.name!r} is not an agent step, so it has no prompt")
        name = step.prompt.relative_to(self.directory).as_posix()
        return self._render(self.environment, item, (name, SUBMIT), self.context(item, step, values, backlog))

    def detail(self, item, step=None, backlog=None):
        """The TUI's view of an item as Markdown, rendered with the same filters and context as its prompts."""
        return self._render(self.views, item, (DETAIL,), self.context(item, step, None, backlog))

    def _render(self, environment, item, templates, context):
        try:
            return "\n".join(environment.get_template(template).render(context) for template in templates)
        except TemplateError as exc:
            where = f" ({exc.filename}:{exc.lineno})" if getattr(exc, "lineno", None) else ""
            raise InvalidTemplate(f"cannot render {templates[0]} for {item.id}: {exc}{where}") from None
