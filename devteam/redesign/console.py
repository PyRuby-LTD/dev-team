"""The redesigned command line, built up beside devteam/cli.py until it replaces it."""
import argparse
import sys
from pathlib import Path

from devteam import git
from devteam.backlog import InvalidRecord, Repository
from devteam.evidence import PathGuard

from . import flow, submission
from .steps import InvalidStep


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
    checkout, backlog = locate(args)
    repo = Repository(backlog, guard=PathGuard(checkout))
    try:
        record = repo.scan().valid.get(args.id)
        if record is None:
            raise InvalidRecord(f"{args.id} is missing or invalid; run validate")
        step = flow.load(record.metadata["workflow"]).steps.get(record.metadata["step"])
        if step is None:
            raise InvalidStep(f"{record.id} is at {record.metadata['step']!r}, which its workflow does not define")
        submission.stage(backlog, record, step, args.outcome, sys.stdin.read())
    except (InvalidRecord, flow.InvalidWorkflow, InvalidStep, OSError, UnicodeError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"{record.id} {step.name}: {args.outcome} staged")


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

    args = parser.parse_args(argv)
    args.func(args)

