import argparse
from pathlib import Path


def cmd_backlog(args):
    from .backlog import InvalidRecord, Repository
    from .workflow import InvalidWorkflow

    repo = Repository(args.workspace)
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

    try:
        Runner(Repository(args.workspace)).run(once=args.once)
    except KeyboardInterrupt:
        pass


def cmd_clean(args):
    from .runner import remove_worktree

    if not remove_worktree(args.workspace, args.id):
        raise SystemExit(f"no worktree for {args.id}")
    print(f"removed worktree for {args.id}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="devteam")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("backlog", help="capture and validate Markdown work items (no agents)")
    p.add_argument("--workspace", required=True, help="root containing epics/stories/tasks/bugs")
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
    p.add_argument("--workspace", required=True)
    p.add_argument("--once", action="store_true", help="exit when no agent-owned step is left, rather than waiting")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("clean", help="remove an item's git worktree")
    p.add_argument("--workspace", required=True)
    p.add_argument("id")
    p.set_defaults(func=cmd_clean)

    args = parser.parse_args(argv)
    args.func(args)
