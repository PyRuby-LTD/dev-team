import argparse
from pathlib import Path

from .config import load_roles
from . import pipeline, workitem


def cmd_backlog(args):
    from .backlog import InvalidRecord, Repository

    repo = Repository(args.workspace)
    try:
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
            print(f"{record.id}  {record.metadata.get('step', '-'):<12} {record.metadata['title']}")
        if snapshot.errors:
            raise SystemExit(1)
    except (InvalidRecord, OSError, UnicodeError) as exc:
        raise SystemExit(str(exc)) from exc


def cmd_new(args):
    request = args.request or Path(args.file).read_text()
    item = workitem.create(request, Path(args.repo))
    print(f"created {item.id} in {item.path}")


def cmd_step(args):
    print(pipeline.step(workitem.load(args.id), load_roles()))


def cmd_run(args):
    item, roles = workitem.load(args.id), load_roles()
    while item["status"] == "ready" and item["stage"] not in pipeline.TERMINAL:
        print(pipeline.step(item, roles))


def cmd_status(args):
    for item in workitem.all_items():
        title = item["title"] or item.artifact("request.md").splitlines()[0][:48]
        print(f"{item.id}  {item['stage']:<12} {item['status']:<14} {title}")


def cmd_show(args):
    item = workitem.load(args.id)
    print(f"{item.id}  {item['title']}")
    print(f"stage={item['stage']} status={item['status']} revisions={item['revisions']}")
    print(f"worktree={item['worktree']} branch={item['branch']}")
    for entry in item["history"]:
        print(f"  {entry['at']}  {entry['stage']:<12} {entry['role']:<14} "
              f"{entry['engine']}/{entry['model']}  exit={entry['exit_code']}")
    for entry in item["human"]:
        print(f"  {entry['at']}  HUMAN {entry['action']}: {entry['note']}")


def cmd_decide(args):
    item = workitem.load(args.id)
    item["human"].append({"at": workitem.now(), "action": args.action, "note": args.note or ""})
    if args.action == "approve":
        item["stage"], item["status"] = "done", "done"
    elif args.action == "revise":
        item["revisions"] += 1
        item["stage"], item["status"] = "implement", "ready"
    elif args.action == "reject":
        item["stage"], item["status"] = "done", "rejected"
    else:  # resume, after answering questions in request.md
        item["status"] = "ready"
    item.save()
    print(f"{item.id} -> stage={item['stage']} status={item['status']}")


def cmd_clean(args):
    item = workitem.load(args.id)
    pipeline.remove_worktree(item)
    print(f"removed worktree for {item.id}")


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

    p = sub.add_parser("new", help="create a work item")
    p.add_argument("request", nargs="?")
    p.add_argument("-f", "--file", help="read the request from a file")
    p.add_argument("-r", "--repo", required=True, help="repository the team works on")
    p.set_defaults(func=cmd_new)

    for name, fn, help_text in [
        ("step", cmd_step, "run the current stage once"),
        ("run", cmd_run, "run stages until a human gate or failure"),
        ("show", cmd_show, "show one item's state and history"),
        ("clean", cmd_clean, "remove an item's git worktree"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("id")
        p.set_defaults(func=fn)

    p = sub.add_parser("status", help="list work items")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("decide", help="record your decision at a gate")
    p.add_argument("id")
    p.add_argument("action", choices=["approve", "revise", "reject", "resume"])
    p.add_argument("-m", "--note")
    p.set_defaults(func=cmd_decide)

    args = parser.parse_args(argv)
    args.func(args)
