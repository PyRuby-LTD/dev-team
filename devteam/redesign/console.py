"""The dev-team command line."""
import argparse
from datetime import datetime, timezone
import sys
from pathlib import Path

from devteam import git
from devteam.config import ROOT, load_roles
from devteam.evidence import PathGuard

from . import flow, submission
from .harness import Harness, record_customer
from .prompt import RUN_VALUES, InvalidPrompt, Prompts
from .steps import AgentStep, InvalidStep
from .work_item import DIRECTORIES, Backlog, InvalidWorkItem, parse

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


def _backlog(args):
    checkout, root = locate(args)
    return Backlog(root, guard=PathGuard(checkout))


def cmd_submit(args):
    backlog = _backlog(args)
    try:
        item = backlog.get(args.id)
        step = backlog.step(item)
        submission.stage(backlog.root, item, step, args.outcome, sys.stdin.read())
    except (InvalidWorkItem, InvalidStep, OSError, UnicodeError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"{item.id} {step.name}: {args.outcome} staged")


def _fields(text):
    fields = submission.parse(text)
    if not isinstance(fields, dict):
        raise InvalidWorkItem("the fields on stdin must be a YAML mapping")
    return fields


def cmd_create(args):
    backlog = _backlog(args)
    try:
        item = backlog.create(args.type, args.title, _fields(sys.stdin.read()))
    except (InvalidWorkItem, InvalidStep, OSError, UnicodeError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"{item.id}: captured" + (f" at {item.step}" if item.step else ""))


def cmd_update(args):
    backlog = _backlog(args)
    try:
        item = backlog.update(args.id, _fields(sys.stdin.read()))
    except (InvalidWorkItem, InvalidStep, OSError, UnicodeError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"{item.id}: updated")


def cmd_record(args):
    backlog = _backlog(args)
    try:
        item = record_customer(backlog, args.id, args.outcome, submission.parse(sys.stdin.read()))
    except (InvalidWorkItem, InvalidStep, OSError, UnicodeError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"{item.id}: {args.outcome} -> {item.step}")


def cmd_run(args):
    try:
        flow.load_all()
    except flow.InvalidWorkflow as exc:
        raise SystemExit(str(exc)) from exc
    checkout, root = locate(args)
    harness = Harness(Backlog(root, guard=PathGuard(checkout)), checkout=checkout)
    try:
        harness.run(once=args.once)
    except KeyboardInterrupt:
        pass
    if harness.failed:
        raise SystemExit(1)


def cmd_check(args):
    from devteam import check

    checkout, root = locate(args)
    directory = checkout or Path(args.product).resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    log = root / "log" / "check" / f"{stamp}.log"
    code, output = check.run(directory, args.test, log)
    # Agents read this, so a pass stays short and a failure shows only its end.
    print(check.tail(output, 8 if code == 0 else check.TAIL_LINES))
    print(f"\ncheck {'passed' if code == 0 else f'FAILED (exit {code})'}; full output: {log.relative_to(directory)}")
    raise SystemExit(code)


def cmd_init(args):
    from devteam.initialise import initialise

    try:
        initialise(Path(args.product).resolve())
    except (git.GitError, OSError) as exc:
        raise SystemExit(str(exc)) from exc


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
        backlog = None
        if args.item:
            backlog = Backlog(locate(args)[1])
            item = backlog.get(args.item)
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
            rendered = prompts.render(item, step, values, backlog)
            print(f"==== {step.name}: {step.owner} ====\n")
            print(f"---- system prompt (roles/{step.role}.md) ----\n")
            print(roles[step.role].brief())
            print(f"---- prompt ({step.prompt.relative_to(prompts.directory.parent).as_posix()}) ----\n")
            print(rendered)
    except (InvalidWorkItem, InvalidStep, InvalidPrompt, flow.InvalidWorkflow, OSError, UnicodeError) as exc:
        raise SystemExit(str(exc)) from exc


def main(argv=None):
    parser = argparse.ArgumentParser(prog="dev-team")
    parser.add_argument("--product", default=".", help="the product repository; its work items live in backlog/ (default: here)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("backlog", help="work items and the outcomes of their steps")
    actions = p.add_subparsers(dest="backlog_action", required=True)
    submit = actions.add_parser("submit", help="stage an agent step's outcome, with its YAML output on stdin")
    submit.add_argument("id")
    submit.add_argument("outcome")
    submit.set_defaults(func=cmd_submit)
    create = actions.add_parser("create", help="capture a work item, with its other fields as YAML on stdin")
    create.add_argument("type", choices=list(DIRECTORIES))
    create.add_argument("title")
    create.set_defaults(func=cmd_create)
    update = actions.add_parser("update", help="replace a work item's fields with those given as YAML on stdin; "
                                               "a null value removes one")
    update.add_argument("id")
    update.set_defaults(func=cmd_update)
    record = actions.add_parser("record", help="record the customer's outcome for an item's step, "
                                               "with its YAML output on stdin")
    record.add_argument("id")
    record.add_argument("outcome")
    record.set_defaults(func=cmd_record)

    p = sub.add_parser("run", help="perform every step an agent or the harness owns, moving items on")
    p.add_argument("--once", action="store_true", help="exit when no step can move, rather than waiting")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("check", help="run the project's check (its Makefile target), or one named test")
    p.add_argument("test", nargs="?", help="a single test to run, as the project's Makefile understands TEST=")
    p.set_defaults(func=cmd_check)

    sub.add_parser("init", help="set up a product with a GitHub origin and backlog").set_defaults(func=cmd_init)

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

