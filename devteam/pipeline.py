import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import ROOT, Role
from . import engines
from .workitem import WorkItem


@dataclass
class Stage:
    name: str
    role: str
    access: str          # "read" or "write"
    in_worktree: bool


STAGES = {
    "intake": Stage("intake", "product_owner", "write", False),
    "investigate": Stage("investigate", "analyst", "read", True),
    "implement": Stage("implement", "implementer", "write", True),
    "review": Stage("review", "reviewer", "read", True),
}

TERMINAL = {"human-gate", "no-change", "done", "blocked"}


def render(stage: str, item: WorkItem) -> str:
    template = (ROOT / "prompts" / f"{stage}.md").read_text()
    review = item.artifact("review.md")
    values = {
        "request": item.artifact("request.md"),
        "intake": item.artifact("intake.md"),
        "investigation": item.artifact("investigation.md"),
        "criteria": item.artifact("criteria.md"),
        "item_dir": str(item.path),
        "worktree": item["worktree"],
        "branch": item["branch"],
        "base": item["base"],
        "revision_notes": (
            f"\n## Review findings to address (revision {item['revisions']})\n{review}"
            if item["revisions"] else ""
        ),
    }
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def ensure_worktree(item: WorkItem) -> Path:
    path = Path(item["worktree"])
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "-C", item["repo"], "worktree", "add", "-b", item["branch"], str(path), item["base"]],
        check=True,
    )
    return path


def remove_worktree(item: WorkItem) -> None:
    path = Path(item["worktree"])
    if path.exists():
        subprocess.run(["git", "-C", item["repo"], "worktree", "remove", "--force", str(path)])
        shutil.rmtree(path, ignore_errors=True)


def step(item: WorkItem, roles: dict[str, Role]) -> str:
    """Run the current stage once and advance. Returns a human-readable outcome."""
    stage_name = item["stage"]
    if stage_name in TERMINAL:
        return f"{item.id} is at {stage_name}; nothing to run"
    if item["status"] == "awaiting-human":
        return f"{item.id} is waiting on you (stage {stage_name})"

    stage = STAGES[stage_name]
    role = roles[stage.role]
    cwd = ensure_worktree(item) if stage.in_worktree else item.path

    (item.path / f"{stage_name}.json").unlink(missing_ok=True)
    item["status"] = "running"
    item.save()

    code = engines.run(role, item, stage_name, render(stage_name, item), cwd, stage.access)
    decision = item.decision(stage_name)

    if code != 0 or decision is None:
        item["status"] = "failed"
        item.save()
        why = f"exit {code}" if code != 0 else f"no valid {stage_name}.json"
        return f"{item.id} {stage_name} failed ({why}) - see {item.path / 'log'}"

    outcome = ADVANCE[stage_name](item, decision)
    item.save()
    return f"{item.id} {stage_name}: {outcome}"


def _intake(item: WorkItem, d: dict) -> str:
    item["title"] = d.get("title") or item["title"]
    if not d.get("ready"):
        item["status"] = "awaiting-human"
        qs = "; ".join(d.get("questions", [])) or "see intake.md"
        return f"needs clarification - {qs}"
    item["stage"], item["status"] = "investigate", "ready"
    return "ready to investigate"


def _investigate(item: WorkItem, d: dict) -> str:
    if not d.get("proceed"):
        item["stage"], item["status"] = "no-change", "awaiting-human"
        return f"no change proposed - {d.get('reason', '')}"
    criteria = d.get("criteria", [])
    (item.path / "criteria.md").write_text("\n".join(f"- {c}" for c in criteria) + "\n")
    item["stage"], item["status"] = "implement", "ready"
    return f"{len(criteria)} acceptance criteria written"


def _implement(item: WorkItem, d: dict) -> str:
    if not d.get("done"):
        item["stage"], item["status"] = "blocked", "awaiting-human"
        return f"blocked - {d.get('notes', '')}"
    item["stage"], item["status"] = "review", "ready"
    checks = "checks passed" if d.get("checks_passed") else "CHECKS FAILED"
    return f"{d.get('summary', 'implemented')} ({checks})"


def _review(item: WorkItem, d: dict) -> str:
    verdict = d.get("verdict", "revise")
    findings = len(d.get("findings", []))
    if verdict == "revise" and item["revisions"] < item["max_revisions"]:
        item["revisions"] += 1
        item["stage"], item["status"] = "implement", "ready"
        return f"revise ({findings} findings), sending back - attempt {item['revisions'] + 1}"
    item["stage"], item["status"] = "human-gate", "awaiting-human"
    return f"{verdict} ({findings} findings) - your call"


ADVANCE = {
    "intake": _intake,
    "investigate": _investigate,
    "implement": _implement,
    "review": _review,
}
