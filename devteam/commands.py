"""The dev-team commands below the command line: each takes what a caller would pipe in and returns what happened."""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from devteam import check as checks
from devteam import engines, git
from devteam.config import ROOT, load_roles
from devteam.evidence import PathGuard

from . import submission
from .steps import AgentStep, InvalidStep
from .workflow import InvalidWorkflow, cached, load_all
from .work_item import Backlog, InvalidWorkItem, parse as parse_item
from .yaml_format import InvalidYaml, parse

EXAMPLE = ROOT / "prompts" / "examples" / "work-item.yaml"
FAILURES = (InvalidWorkItem, InvalidStep, InvalidWorkflow, git.GitError, OSError, UnicodeError)


class CommandFailed(Exception):
    """The command could not do what was asked; the message says why."""


@dataclass(frozen=True)
class Prompt:
    step: AgentStep
    brief: str
    text: str
    source: str


@dataclass(frozen=True)
class CheckRun:
    code: int
    output: str
    log: Path


def _yaml(text, what):
    try:
        return parse(text)
    except InvalidYaml as exc:
        raise InvalidWorkItem(f"{what} must be valid YAML: {exc}") from None


def _fields(text):
    fields = _yaml(text, "the fields")
    if not isinstance(fields, dict):
        raise InvalidWorkItem("the fields must be a YAML mapping")
    return fields


class DevTeam:
    """The commands for one product, whose work items live in its backlog."""

    def __init__(self, product=".", engine=engines.run, report=print):
        self.product = Path(product).resolve()
        self.engine = engine
        self.report = report

    def locate(self):
        """The product's checkout (None outside git) and its backlog directory."""
        top = git.checkout(self.product)
        if top is None:
            return None, self.product / git.BACKLOG_DIR
        try:
            return top, git.ensure_backlog(top, create=False)
        except git.GitError as exc:
            raise CommandFailed(str(exc)) from None

    def backlog(self):
        checkout, root = self.locate()
        return Backlog(root, guard=PathGuard(checkout))

    def launch(self):
        """Load the harness's workflows and check the product is set up before anything runs in it."""
        from devteam.initialise import missing

        try:
            load_all()
        except InvalidWorkflow as exc:
            raise CommandFailed(str(exc)) from None
        gaps = missing(self.product)
        if gaps:
            raise CommandFailed(f"{self.product} is not set up for dev-team:\n" + "\n".join(f"  {gap}" for gap in gaps))
        return self.locate()

    def harness(self):
        from .harness import Harness

        checkout, root = self.launch()
        return Harness(Backlog(root, guard=PathGuard(checkout)), checkout=checkout, engine=self.engine,
                       report=self.report)

    def submit(self, item_id, outcome, output=""):
        """Stage an agent step's outcome, checked at once; the harness records it once the agent exits."""
        backlog = self.backlog()
        try:
            item = backlog.get(item_id)
            step = backlog.step(item)
            submission.stage(backlog.root, item, step, outcome, output)
        except FAILURES as exc:
            raise CommandFailed(str(exc)) from None
        return item, step

    def create(self, kind, title, fields=""):
        try:
            return self.backlog().create(kind, title, _fields(fields))
        except FAILURES as exc:
            raise CommandFailed(str(exc)) from None

    def update(self, item_id, fields):
        try:
            return self.backlog().update(item_id, _fields(fields))
        except FAILURES as exc:
            raise CommandFailed(str(exc)) from None

    def record(self, item_id, outcome, output=""):
        """Record the customer's outcome for an item's step."""
        from .harness import record_customer

        try:
            return record_customer(self.backlog(), item_id, outcome, _yaml(output, "the step's output"))
        except FAILURES as exc:
            raise CommandFailed(str(exc)) from None

    def run(self, once=False):
        """Perform every step an agent or the harness owns; the items that failed, with why."""
        harness = self.harness()
        try:
            harness.run(once=once)
        except KeyboardInterrupt:
            pass
        return harness.failed

    def check(self, test=None):
        checkout, root = self.locate()
        directory = checkout or self.product
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        log = root / "log" / "check" / f"{stamp}.log"
        code, output = checks.run(directory, test, log)
        return CheckRun(code, output, log.relative_to(directory))

    def init(self):
        from devteam.initialise import initialise

        try:
            initialise(self.product, self.report)
        except (git.GitError, OSError) as exc:
            raise CommandFailed(str(exc)) from None

    def prompts(self, step=None, item=None, file=None, values=None):
        """What each agent step of the item's workflow would be given, without running an agent."""
        from .template import RUN_VALUES, InvalidTemplate, Templates

        try:
            backlog = None
            if item:
                backlog = Backlog(self.locate()[1])
                work_item = backlog.get(item)
            else:
                work_item = parse_item(Path(file or EXAMPLE).read_text(encoding="utf-8"))
            if work_item.workflow is None:
                raise InvalidWorkItem(f"{work_item.id} is not in a workflow")
            workflow = cached(work_item.workflow)
            if step is None:
                chosen = [each for each in workflow.steps.values() if isinstance(each, AgentStep)]
            elif not isinstance(workflow.steps.get(step), (AgentStep, type(None))):
                raise InvalidStep(f"step {step!r} is not an agent step, so it has no prompt")
            elif step in workflow.steps:
                chosen = [workflow.steps[step]]
            else:
                raise InvalidStep(f"workflow {work_item.workflow!r} has no step {step!r}")
            templates = Templates()
            roles = load_roles()
            values = {**{name: f"<{name}>" for name in RUN_VALUES}, **(values or {})}
            return [Prompt(each, roles[each.role].brief(), templates.prompt(work_item, each, values, backlog),
                           each.prompt.relative_to(templates.directory.parent).as_posix())
                    for each in chosen]
        except (*FAILURES, InvalidTemplate) as exc:
            raise CommandFailed(str(exc)) from None
