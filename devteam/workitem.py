import json
from datetime import datetime, timezone
from pathlib import Path

from .config import workspace

WORK = workspace() / "work"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class WorkItem:
    def __init__(self, path: Path):
        self.path = path
        self.state = json.loads((path / "state.json").read_text())

    @property
    def id(self) -> str:
        return self.state["id"]

    def __getitem__(self, key):
        return self.state[key]

    def __setitem__(self, key, value):
        self.state[key] = value

    def save(self) -> None:
        self.state["updated"] = now()
        (self.path / "state.json").write_text(json.dumps(self.state, indent=2) + "\n")

    def artifact(self, name: str) -> str:
        f = self.path / name
        return f.read_text().strip() if f.exists() else "(not available)"

    def decision(self, stage: str) -> dict | None:
        f = self.path / f"{stage}.json"
        if not f.exists():
            return None
        try:
            return json.loads(f.read_text())
        except json.JSONDecodeError:
            return None

    def record(self, **entry) -> None:
        self.state.setdefault("history", []).append({"at": now(), **entry})


def next_id() -> str:
    existing = [int(p.name.split("-")[1]) for p in WORK.glob("ITEM-*") if p.is_dir()]
    return f"ITEM-{max(existing, default=0) + 1:03d}"


def create(request: str, repo: Path) -> WorkItem:
    WORK.mkdir(parents=True, exist_ok=True)
    item_id = next_id()
    path = WORK / item_id
    (path / "log").mkdir(parents=True)
    (path / "request.md").write_text(request.strip() + "\n")
    state = {
        "id": item_id,
        "title": None,
        "stage": "intake",
        "status": "ready",
        "created": now(),
        "updated": now(),
        "repo": str(repo.resolve()),
        "base": current_branch(repo),
        "branch": f"devteam/{item_id}",
        "worktree": str(WORK.parent / "worktrees" / item_id),
        "revisions": 0,
        "max_revisions": 2,
        "history": [],
        "human": [],
    }
    (path / "state.json").write_text(json.dumps(state, indent=2) + "\n")
    return WorkItem(path)


def current_branch(repo: Path) -> str:
    import subprocess

    out = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    )
    return out.stdout.strip() or "main"


def load(item_id: str) -> WorkItem:
    path = WORK / item_id
    if not (path / "state.json").exists():
        raise SystemExit(f"no such work item: {item_id}")
    return WorkItem(path)


def all_items() -> list[WorkItem]:
    return [WorkItem(p) for p in sorted(WORK.glob("ITEM-*")) if (p / "state.json").exists()]
