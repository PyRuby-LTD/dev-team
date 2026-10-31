"""The redesigned command line, built up beside devteam/cli.py until it replaces it."""
import argparse
import sys
from pathlib import Path

from devteam import git
from devteam.config import ROOT, load_roles
from devteam.evidence import PathGuard

from . import flow, submission
from .prompt import RUN_VALUES, InvalidPrompt, Prompts
from .steps import AgentStep, InvalidStep
from .work_item import Backlog, InvalidWorkItem, parse

EXAMPLE = ROOT / "prompts" / "examples" / "work-item.yaml"


def locate(args):
    """The product's checkout (None outside git) and its backlog directory."""
    directory = Path(args.product).resolve()
    top = git.checkout(directory)
    if top is None:
        return None, directory / git.BACKLOG_DIR
    try:
        return top, git.ensure_backlog(top)
    except git.GitError as exc:
        raise SystemExit(str(exc)) from exc


def cmd_submit(args):
    checkout, root = locate(args)
    backlog = Backlog(root, guard=PathGuard(checkout))
    try:
        item = backlog.get(args.id)
        step = backlog.step(item)
        submission.stage(root, item, step, args.outcome, sys.stdin.read())
    except (InvalidWorkItem, InvalidStep, OSError, UnicodeError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"{item.id} {step.name}: {args.outcome} staged")


def _values(pairs):
    values = {name: f"<{name}>" for name in RUN_VALUES}
    for pair in pairs:
        name, sep, value = pair.partition("=")
        if not sep:
            raise SystemExit(f"--set takes name=value, not {pair!r}")
        values[name] = value
    return values


def cmd_prompt(args):
    """Print what each agent step's role would be given, for reviewing the prompts."""
    try:
        if args.item:
            item = Backlog(locate(args)[1]).get(args.item)
        else:
            item = parse(Path(args.file or EXAMPLE).read_text(encoding="utf-8"))
        if item.workflow is None:
            raise InvalidWorkItem(f"{item.id} is not in a workflow")
        workflow = flow.load(item.workflow)
        if args.step is None:
            steps = [step for step in workflow.steps.values() if isinstance(step, AgentStep)]
        elif args.step in workflow.steps:
            steps = [workflow.steps[args.step]]
        else:
            raise InvalidStep(f"workflow {item.workflow!r} has no step {args.step!r}")
        prompts = Prompts()
        roles = load_roles()
        values = _values(args.set)
        for step in steps:
            rendered = prompts.render(item, step, values)
            print(f"==== {step.name}: {step.owner} ====\n")
            print(f"---- system prompt (roles/{step.role}.md) ----\n")
            print(roles[step.role].brief())
            print(f"---- prompt ({step.prompt.relative_to(prompts.directory.parent).as_posix()}) ----\n")
            print(rendered)
    except (InvalidWorkItem, InvalidStep, InvalidPrompt, flow.InvalidWorkflow, OSError, UnicodeError) as exc:
        raise SystemExit(str(exc)) from exc


def main(argv=None):
    parser = argparse.ArgumentParser(prog="devteam")
    parser.add_argument("--product", default=".", help="the product repository; its work items live in backlog/ (default: here)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("backlog", help="work items and the outcomes of their steps")
    actions = p.add_subparsers(dest="backlog_action", required=True)
    submit = actions.add_parser("submit", help="stage an agent step's outcome, with its YAML output on stdin")
    submit.add_argument("id")
    submit.add_argument("outcome")
    submit.set_defaults(func=cmd_submit)

    p = sub.add_parser("prompt", help="print the prompts agent steps would be given, to review them")
    p.add_argument("step", nargs="?", help="one agent step (default: every agent step in the item's workflow)")
    source = p.add_mutually_exclusive_group()
    source.add_argument("--item", help="a work item in the backlog")
    source.add_argument("--file", help="a work-item YAML file (default: prompts/examples/work-item.yaml)")
    p.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                   help="a run value such as branch=devteam/STORY-001; unset ones print as <name>")
    p.set_defaults(func=cmd_prompt)

    args = parser.parse_args(argv)
    args.func(args)

