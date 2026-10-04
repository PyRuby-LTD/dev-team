"""Runs agent-owned steps: invoke the owning role, then apply the transition it names."""
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from . import engines
from .backlog import InvalidRecord
from .config import ROOT, load_roles
from .workflow import InvalidWorkflow

REPLY = re.compile(r"TRANSITION:\s*([A-Za-z0-9_-]+)\W*\Z")

PROTOCOL = """
## Work item

The work item is the file {{item}}. Read it first; it is the full context.
You may edit the body of that file. Do not change its front matter.

## Finishing

End your reply with a single line `TRANSITION: <name>`, where <name> is one of:

{{transitions}}
"""


class StepFailed(Exception):
    pass


def _git(directory, *args):
    return subprocess.run(["git", "-C", str(directory), *args], capture_output=True, text=True)


def checkout(root):
    out = _git(root, "rev-parse", "--show-toplevel")
    return Path(out.stdout.strip()) if out.returncode == 0 else None


def ensure_worktree(root, item_id):
    path = root / "worktrees" / item_id
    if path.exists():
        return path
    repo = checkout(root)
    if repo is None:
        raise StepFailed(f"{root} is not inside a git repository, which this role's worktree needs")
    branch = f"devteam/{item_id}"
    if _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0:
        out = _git(repo, "worktree", "add", str(path), branch)
    else:
        out = _git(repo, "worktree", "add", "-b", branch, str(path), "HEAD")
    if out.returncode:
        raise StepFailed("could not create the worktree: " + out.stderr.strip())
    return path


def remove_worktree(root, item_id):
    root = Path(root).resolve()
    path = root / "worktrees" / item_id
    repo = checkout(root)
    if repo is None or not path.exists():
        return False
    return _git(repo, "worktree", "remove", "--force", str(path)).returncode == 0


def render(step, values):
    template = ROOT / "prompts" / f"{step.name}.md"
    text = (template.read_text() if template.exists() else "") + PROTOCOL
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


class Runner:
    def __init__(self, repository, roles=None, engine=engines.run, report=print, max_runs=8):
        self.repository = repository
        self.roles = load_roles() if roles is None else roles
        self.engine = engine
        self.report = report
        self.max_runs = max_runs
        self.failed = {}
        self.runs = {}

    def pending(self):
        found = []
        for record in self.repository.scan().valid.values():
            if record.metadata["type"] == "epic" or record.id in self.failed:
                continue
            step = self.repository.step(record)
            if step.role:
                found.append((record, step))
        return found

    def invoke(self, record, step, log):
        root = self.repository.root
        role = self.roles[step.role]
        # A revise loop between two agents would otherwise run unattended without limit.
        self.runs[record.id] = self.runs.get(record.id, 0) + 1
        if self.runs[record.id] > self.max_runs:
            raise StepFailed(f"already ran {self.max_runs} agent steps this session")
        values = {
            "item": str(record.path),
            "id": record.id,
            "transitions": "\n".join(f"- `{name}` moves the item to `{target}`" for name, target in step.transitions.items()),
        }
        if role.worktree:
            cwd = ensure_worktree(root, record.id)
            base = _git(checkout(root), "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
            values.update(worktree=str(cwd), branch=f"devteam/{record.id}", base=base)
        else:
            cwd = checkout(root) or root
        log.parent.mkdir(parents=True, exist_ok=True)
        code, reply = self.engine(role, render(step, values), cwd, root, log)
        if code != 0:
            raise StepFailed(f"exit {code}")
        lines = reply.strip().splitlines()
        match = REPLY.search(lines[-1]) if lines else None
        if match is None:
            raise StepFailed("the reply did not end with a TRANSITION line")
        if match.group(1) not in step.transitions:
            raise StepFailed(f"the reply named {match.group(1)!r}, which is not a transition from {step.name!r}")
        current = self.repository.scan().valid.get(record.id)
        if current is None or current.metadata != record.metadata:
            raise StepFailed("the agent changed or broke the item's front matter")
        return match.group(1), self.repository.transition(record.id, match.group(1))

    def run_item(self, record, step):
        role = self.roles[step.role]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        log = self.repository.root / "log" / record.id / f"{step.name}-{stamp}.log"
        label = f"{record.id} {step.name} ({role.name} via {role.engine}/{role.model})"
        self.report(f"{label}: running")
        try:
            name, updated = self.invoke(record, step, log)
        except (StepFailed, InvalidRecord, InvalidWorkflow, OSError) as exc:
            self.failed[record.id] = str(exc)
            self.report(f"{label}: FAILED - {exc}; still at {step.name}, not retried until restart; see {log}")
            return
        self.report(f"{label}: {name} -> {updated.metadata['step']}")

    def run_pass(self):
        pending = self.pending()
        for record, step in pending:
            self.run_item(record, step)
        return len(pending)

    def run(self, once=False, interval=2.0):
        while True:
            if self.run_pass() == 0:
                if once:
                    return
                time.sleep(interval)
