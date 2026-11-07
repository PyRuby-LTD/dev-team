"""The dev-team command line: arguments, stdin, stdout and exit codes around the commands."""
import argparse
import sys

from devteam import check

from .commands import CommandFailed, DevTeam
from .work_item import DIRECTORIES


def cmd_submit(team, args):
    item, step = team.submit(args.id, args.outcome, sys.stdin.read())
    print(f"{item.id} {step.name}: {args.outcome} staged")


def cmd_create(team, args):
    item = team.create(args.type, args.title, sys.stdin.read())
    print(f"{item.id}: captured" + (f" at {item.step}" if item.step else ""))


def cmd_update(team, args):
    print(f"{team.update(args.id, sys.stdin.read()).id}: updated")


def cmd_record(team, args):
    item = team.record(args.id, args.outcome, sys.stdin.read())
    print(f"{item.id}: {args.outcome} -> {item.step}")


def cmd_run(team, args):
    if team.run(once=args.once):
        raise SystemExit(1)


def cmd_tui(team, args):
    from .tui import run

    # The harness writes from its own thread, so it gets its own backlog whose notices it routes to the screen.
    harness = team.harness()
    run(team.backlog(), harness)


def cmd_check(team, args):
    result = team.check(args.test)
    # Agents read this, so a pass stays short and a failure shows only its end.
    print(check.tail(result.output, 8 if result.code == 0 else check.TAIL_LINES))
    print(f"\ncheck {'passed' if result.code == 0 else f'FAILED (exit {result.code})'}; full output: {result.log}")
    raise SystemExit(result.code)


def cmd_init(team, args):
    team.init()


def _values(pairs):
    values = {}
    for pair in pairs:
        name, sep, value = pair.partition("=")
        if not sep:
            raise SystemExit(f"--set takes name=value, not {pair!r}")
        values[name] = value
    return values


def cmd_prompt(team, args):
    """Print what each agent step's role would be given, for reviewing the prompts."""
    for prompt in team.prompts(args.step, item=args.item, file=args.file, values=_values(args.set)):
        print(f"==== {prompt.step.name}: {prompt.step.owner} ====\n")
        print(f"---- system prompt (roles/{prompt.step.role}.md) ----\n")
        print(prompt.brief)
        print(f"---- prompt ({prompt.source}) ----\n")
        print(prompt.text)


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

    sub.add_parser("tui", help="the customer's view of the backlog, with the harness running behind it"
                   ).set_defaults(func=cmd_tui)

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
    try:
        args.func(DevTeam(args.product), args)
    except CommandFailed as exc:
        raise SystemExit(str(exc)) from None

