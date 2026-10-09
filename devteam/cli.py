import argparse
from pathlib import Path

from .evidence import PathGuard


def locate(args):
    """The product's checkout (None outside git) and its backlog directory."""
    from . import git

    directory = Path(args.product).resolve()
    top = git.checkout(directory)
    if top is None:
        return None, directory / git.BACKLOG_DIR
    try:
        return top, git.ensure_backlog(top)
    except git.GitError as exc:
        raise SystemExit(str(exc)) from exc


def cmd_backlog(args):
    from .backlog import InvalidRecord, Repository
    from .workflow import InvalidWorkflow

    checkout, backlog = locate(args)
    repo = Repository(backlog, guard=PathGuard(checkout), notice=print)
    try:
        if args.backlog_action == "move":
            record = repo.transition(args.id, args.transition, args.note or "")
            print(f"{record.id} -> {record.metadata['step']} ({repo.step(record).owner})")
            return
        if args.backlog_action == "capture":
            body = Path(args.file).read_bytes().decode("utf-8") if args.file else ""
            record = repo.create(args.type, args.title, body, parent=args.parent, item_id=args.id)
            print(f"created {record.id} in {record.path}")
            return
        snapshot = repo.scan()
        for path, errors in snapshot.errors.items():
            for error in errors:
                print(f"{path}: ERROR: {error}")
        for record in snapshot.valid.values():
            step = repo.step(record) if "step" in record.metadata else None
            print(f"{record.id:<10} {step.name if step else '-':<12} "
                  f"{'-' if step is None or step.terminal else step.owner:<18} {record.metadata['title']}")
        if snapshot.errors:
            raise SystemExit(1)
    except (InvalidRecord, InvalidWorkflow, OSError, UnicodeError) as exc:
        raise SystemExit(str(exc)) from exc


def cmd_run(args):
    from .backlog import Repository
    from .runner import Runner

    checkout, backlog = locate(args)
    try:
        Runner(Repository(backlog, guard=PathGuard(checkout)), checkout=checkout).run(once=args.once)
    except KeyboardInterrupt:
        pass


def cmd_tui(args):
    from . import tui
    from .backlog import Repository

    from .runner import Runner

    checkout, backlog = locate(args)
    tui.run(Repository(backlog, guard=PathGuard(checkout)),
            Runner(Repository(backlog, guard=PathGuard(checkout)), checkout=checkout))


def cmd_check(args):
    from datetime import datetime, timezone
    from . import check

    checkout, backlog = locate(args)
    directory = checkout or Path(args.product).resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    log = backlog / "log" / "check" / f"{stamp}.log"
    code, output = check.run(directory, args.test, log)
    # Agents read this, so a pass stays short and a failure shows only its end.
    print(check.tail(output, 8 if code == 0 else check.TAIL_LINES))
    print(f"\ncheck {'passed' if code == 0 else f'FAILED (exit {code})'}; full output: {log.relative_to(directory)}")
    raise SystemExit(code)


def cmd_init(args):
    from . import git
    from .initialise import initialise

    try:
        initialise(Path(args.product).resolve())
    except (git.GitError, OSError) as exc:
        raise SystemExit(str(exc)) from exc


def main(argv=None):
    parser = argparse.ArgumentParser(prog="devteam")
    parser.add_argument("--product", default=".", help="the product repository; its work items live in backlog/ (default: here)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("backlog", help="capture and validate Markdown work items (no agents)")
    actions = p.add_subparsers(dest="backlog_action", required=True)
    actions.add_parser("validate", help="validate work items and report errors").set_defaults(func=cmd_backlog)
    actions.add_parser("list", help="list work items with their step and owner").set_defaults(func=cmd_backlog)
    capture = actions.add_parser("capture", help="create a Markdown work item")
    capture.add_argument("type", choices=["epic", "story", "task", "bug", "request"])
    capture.add_argument("title")
    capture.add_argument("--id")
    capture.add_argument("--parent")
    capture.add_argument("--file", help="UTF-8 Markdown body; metadata is generated separately")
    capture.set_defaults(func=cmd_backlog)
    move = actions.add_parser("move", help="apply one of the current step's transitions")
    move.add_argument("id")
    move.add_argument("transition")
    move.add_argument("-m", "--note", help="feedback for the next owner, recorded in the item body")
    move.set_defaults(func=cmd_backlog)

    p = sub.add_parser("run", help="invoke the owning agent for every item at an agent-owned step")
    p.add_argument("--once", action="store_true", help="exit when no agent-owned step can run, rather than waiting")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("tui", help="see every work item, answer questions and move items along")
    p.set_defaults(func=cmd_tui)

    p = sub.add_parser("check", help="run the project's check (its Makefile target), or one named test")
    p.add_argument("test", nargs="?", help="a single test to run, as the project's Makefile understands TEST=")
    p.set_defaults(func=cmd_check)

    sub.add_parser("init", help="set up a product with a GitHub origin and backlog").set_defaults(func=cmd_init)
    sub.add_parser("help", help="show commands and backlog actions").set_defaults(
        func=lambda args: (parser.print_help(), sub.choices["backlog"].print_help()))

    args = parser.parse_args(argv)
    if args.cmd in {"run", "tui", "init"}:
        from .config import harness_command

        try:
            harness_command()
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    args.func(args)
