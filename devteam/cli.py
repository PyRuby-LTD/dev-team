import argparse
from pathlib import Path


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

    repo = Repository(locate(args)[1])
    try:
        if args.backlog_action == "move":
            record = repo.transition(args.id, args.transition)
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
        Runner(Repository(backlog), checkout=checkout).run(once=args.once)
    except KeyboardInterrupt:
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(prog="devteam")
    parser.add_argument("--product", default=".", help="the product repository; its work items live in backlog/ (default: here)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("backlog", help="capture and validate Markdown work items (no agents)")
    actions = p.add_subparsers(dest="backlog_action", required=True)
    actions.add_parser("validate").set_defaults(func=cmd_backlog)
    capture = actions.add_parser("capture")
    capture.add_argument("type", choices=["epic", "story", "task", "bug"])
    capture.add_argument("title")
    capture.add_argument("--id")
    capture.add_argument("--parent")
    capture.add_argument("--file", help="UTF-8 Markdown body; metadata is generated separately")
    capture.set_defaults(func=cmd_backlog)
    move = actions.add_parser("move", help="apply one of the current step's transitions")
    move.add_argument("id")
    move.add_argument("transition")
    move.set_defaults(func=cmd_backlog)

    p = sub.add_parser("run", help="invoke the owning agent for every item at an agent-owned step")
    p.add_argument("--once", action="store_true", help="exit when no agent-owned step can run, rather than waiting")
    p.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)
    args.func(args)
