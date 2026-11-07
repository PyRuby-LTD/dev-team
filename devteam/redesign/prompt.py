"""Agent prompts: Jinja2 templates in prompts/, rendered with the work item, its pending feedback and its standards."""
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError
import yaml

from devteam.config import ROOT, harness_command

from .steps import AgentStep
from .work_item import Requirements, to_yaml

RUN_VALUES = ("checkout", "branch", "base", "verify_log", "conflicted_files", "evidence_dir")
SUBMIT = "_submit.md"


class InvalidPrompt(ValueError):
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
    """The customer's choice when playing the item, or else the standards analysis proposed."""
    names = None
    for entry in reversed(item.step_outputs):
        listed = entry.output.get("standards")
        if isinstance(listed, list) and all(isinstance(name, str) for name in listed):
            names = listed
            break
    if names is None:
        names = [choice.name for choice in item.standards or []]
    unknown = [name for name in names if name not in available]
    if unknown:
        raise InvalidPrompt(f"{item.id} names standards that do not exist: {', '.join(unknown)}")
    return [available[name] for name in names]


class Prompts:
    def __init__(self, directory=None, standards=None):
        self.directory = Path(directory or ROOT / "prompts").resolve()
        self.standards = load_standards(standards)
        self.environment = Environment(loader=FileSystemLoader(self.directory), undefined=StrictUndefined,
                                       trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True,
                                       autoescape=False)
        self.environment.filters["yaml"] = to_yaml

    def context(self, item, step, values=None, backlog=None):
        return {
            "item": item,
            "step": step,
            "pending": item.pending(step.name),
            "work_items": [backlog.get(i) for i in item.work_items or []] if backlog else [],
            "requirements": Requirements.model_validate(item.model_dump(include=set(Requirements.model_fields))),
            "standards": chosen_standards(item, self.standards),
            "available_standards": list(self.standards.values()),
            "requirement_fields": list(Requirements.model_fields),
            "harness_command": harness_command("devteam.redesign"),
            **(values or {}),
        }

    def render(self, item, step, values=None, backlog=None):
        """The step's prompt followed by the instructions for submitting its outcome."""
        if not isinstance(step, AgentStep):
            raise InvalidPrompt(f"step {step.name!r} is not an agent step, so it has no prompt")
        context = self.context(item, step, values, backlog)
        name = step.prompt.relative_to(self.directory).as_posix()
        try:
            return "\n".join(self.environment.get_template(template).render(context) for template in (name, SUBMIT))
        except TemplateError as exc:
            where = f" ({exc.filename}:{exc.lineno})" if getattr(exc, "lineno", None) else ""
            raise InvalidPrompt(f"cannot render {name} for {item.id}: {exc}{where}") from None
