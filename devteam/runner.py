"""Runs agent-owned steps: invoke the owning role, then apply the transition it names."""
import re
import time
from datetime import datetime, timezone

from . import engines, git
from .backlog import InvalidRecord
from .config import ROOT, load_roles
from .workflow import InvalidWorkflow

REPLY = re.compile(r"TRANSITION:\s*([A-Za-z0-9_-]+)\W*\Z")
RECORDS = "docs/work-items"

PROTOCOL = """
## Work item

The work item is the file {{item}}. Read it first; it is the full context.
You may edit the body of that file. Do not change its front matter.
If it has a `## Feedback` section, the last entry there is the customer's reason
for sending the item to you; act on it.

## Finishing

End your reply with a single line `TRANSITION: <name>`, where <name> is one of:

{{transitions}}
"""


class StepFailed(Exception):
    pass


class Waiting(Exception):
    pass


def render(step, values):
    template = ROOT / "prompts" / f"{step.name}.md"
    text = (template.read_text() if template.exists() else "") + PROTOCOL
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


class Runner:
    def __init__(self, repository, roles=None, engine=engines.run, report=print, max_runs=8, checkout=None):
        self.repository = repository
        self.roles = load_roles() if roles is None else roles
        self.engine = engine
        self.report = report
        self.max_runs = max_runs
        self.checkout = checkout
        self.failed = {}
        self.waiting = {}
        self.active = None
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

    def take_checkout(self, record):
        """Put the checkout on the item's branch; one unfinished item holds it at a time."""
        if self.checkout is None:
            raise StepFailed("this role works on a branch, which needs a git repository")
        branch = f"devteam/{record.id}"
        current = git.current_branch(self.checkout)
        if current == branch:
            return branch
        if current is None:
            raise StepFailed("the checkout is not on a branch")
        if current.startswith("devteam/"):
            holder = self.repository.scan().valid.get(current.removeprefix("devteam/"))
            if holder is not None and not self.repository.step(holder).terminal:
                raise Waiting(f"waiting for {holder.id}, which holds the checkout at step {holder.metadata['step']}")
        if not git.clean(self.checkout):
            raise Waiting(f"waiting: the checkout has uncommitted changes on {current}")
        if current.startswith("devteam/"):
            base = git.base_of(self.checkout, current)
            if base is None:
                raise StepFailed(f"no base branch is recorded for {current}; switch branch by hand")
            git.must(self.checkout, "switch", "-q", base)
            current = base
        if git.has_ref(self.checkout, f"refs/heads/{branch}"):
            git.must(self.checkout, "switch", "-q", branch)
        else:
            git.must(self.checkout, "switch", "-q", "-c", branch)
            git.must(self.checkout, "config", f"branch.{branch}.base", current)
        return branch

    def invoke(self, record, step, log):
        root = self.repository.root
        role = self.roles[step.role]
        values = {
            "item": str(record.path),
            "id": record.id,
            "transitions": "\n".join(f"- `{name}` moves the item to `{target}`" for name, target in step.transitions.items()),
        }
        if role.branch:
            branch = self.take_checkout(record)
            base = git.base_of(self.checkout, branch)
            if base is None:
                raise StepFailed(f"no base branch is recorded for {branch}")
            values.update(checkout=str(self.checkout), branch=branch, base=base)
        # A revise loop between two agents would otherwise run unattended without limit.
        if self.runs.get(record.id, 0) >= self.max_runs:
            raise StepFailed(f"already ran {self.max_runs} agent steps this session")
        self.runs[record.id] = self.runs.get(record.id, 0) + 1
        if role.record:
            copy = self.checkout / RECORDS / f"{record.id}.md"
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes(record.path.read_bytes())
            git.commit_all(self.checkout, f"{record.id}: record the work item", str(copy))
        log.parent.mkdir(parents=True, exist_ok=True)
        self.active = record.id
        self.report(f"{record.id} {step.name}: {role.name} started")
        try:
            code, reply = self.engine(role, render(step, values), self.checkout or root, root, log)
        finally:
            self.active = None
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
        # Agents often cannot write .git from their sandbox, so the runner commits their work.
        if role.branch and not git.clean(self.checkout):
            git.commit_all(self.checkout, f"{record.id}: {step.name} by {role.name}")
        return match.group(1), self.repository.transition(record.id, match.group(1))

    def run_item(self, record, step):
        role = self.roles[step.role]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        log = self.repository.root / "log" / record.id / f"{step.name}-{stamp}.log"
        label = f"{record.id} {step.name} ({role.name} via {role.engine}/{role.model})"
        try:
            name, updated = self.invoke(record, step, log)
        except Waiting as reason:
            if self.waiting.get(record.id) != str(reason):
                self.waiting[record.id] = str(reason)
                self.report(f"{label}: {reason}")
            return False
        except (StepFailed, git.GitError, InvalidRecord, InvalidWorkflow, OSError) as exc:
            self.failed[record.id] = str(exc)
            self.report(f"{label}: FAILED - {exc}; still at {step.name}, not retried until restart; see {log}")
            try:
                self.repository.commit(f"{record.id}: {step.name} failed")
            except InvalidRecord:
                pass
            return True
        self.waiting.pop(record.id, None)
        self.report(f"{label}: {name} -> {updated.metadata['step']}")
        return True

    def retry(self, item_id):
        self.failed.pop(item_id, None)
        self.runs.pop(item_id, None)

    def run_pass(self):
        return sum(self.run_item(record, step) for record, step in self.pending())

    def run(self, once=False, interval=2.0):
        while True:
            if self.run_pass() == 0:
                if once:
                    return
                time.sleep(interval)
