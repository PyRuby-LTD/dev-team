"""The harness loop: perform each step the harness or an agent owns, then record its outcome and move the item on."""
from datetime import datetime, timezone
import threading
import time

from devteam import check as checks
from devteam import engines, git
from devteam.config import load_roles

from .template import Templates
from .steps import Check, InvalidStep, StepFailed, Waiting
from .work_item import MovedOn

BRANCH_PREFIX = "devteam/"


def branch_of(item):
    return f"{BRANCH_PREFIX}{item.id}"


def record_customer(backlog, item_id, outcome, output):
    item = backlog.get(item_id)
    step = backlog.step(item)
    if outcome not in step.customer_outcomes:
        if not step.customer_outcomes:
            raise InvalidStep(f"{item.id} is at step {step.name!r}, which {step.owner} performs, not the customer")
        if outcome in step.outcomes:
            raise InvalidStep(f"{step.owner} decides {outcome!r} at step {step.name!r}; you may choose "
                              + ", ".join(step.customer_outcomes))
    return backlog.record(item.id, outcome, output, at=step.name)


class Harness:
    def __init__(self, backlog, checkout=None, roles=None, templates=None, engine=engines.run, check=checks.run,
                 report=print):
        self.backlog = backlog
        self.checkout = checkout
        self.roles = load_roles() if roles is None else roles
        self.templates = templates or Templates()
        self.engine = engine
        self.check = check
        self.report = report
        self.on_line = None
        self.failed = {}
        self.waiting = {}
        self.not_before = {}

    def values(self, item):
        evidence = self.backlog.root / "log" / item.id
        check_steps = [step.name for step in self.backlog.workflow(item.workflow).steps.values() if isinstance(step, Check)]
        # The stamp after the step name orders logs of different check steps by when they ran.
        logs = sorted((log for name in check_steps for log in evidence.glob(f"{name}-*.log")),
                      key=lambda log: log.stem.rsplit("-", 1)[-1])
        values = {"checkout": str(self.checkout or self.backlog.root), "evidence_dir": str(evidence),
                  "verify_log": str(logs[-1]) if logs else "not yet written: no workflow check has run"}
        branch = branch_of(item)
        if self.checkout is not None and git.has_ref(self.checkout, f"refs/heads/{branch}"):
            values.update(branch=branch, base=git.base_of(self.checkout, branch) or "")
        return values

    def holder(self):
        current = git.current_branch(self.checkout)
        if not (current and current.startswith(BRANCH_PREFIX)):
            return None
        holder = self.backlog.scan().valid.get(current.removeprefix(BRANCH_PREFIX))
        if holder is None or holder.workflow is None or not self.backlog.step(holder).uses_checkout(self):
            return None
        return holder

    def take_checkout(self, item):
        if self.checkout is None:
            raise StepFailed("this step works on the item's branch, which needs a git repository")
        branch = branch_of(item)
        current = git.current_branch(self.checkout)
        if current == branch:
            return
        if current is None:
            raise StepFailed("the checkout is not on a branch")
        holder = self.holder()
        if holder is not None:
            raise Waiting(f"waiting for the checkout, which {holder.id} holds at step {holder.step}")
        if not git.clean(self.checkout):
            raise Waiting(f"waiting for the checkout, which has uncommitted changes on {current}")
        if current.startswith(BRANCH_PREFIX):
            base = git.base_of(self.checkout, current)
            if base is None:
                raise StepFailed(f"no base branch is recorded for {current}; switch the checkout by hand")
            git.must(self.checkout, "switch", "-q", base)
            current = base
        if git.has_ref(self.checkout, f"refs/heads/{branch}"):
            git.must(self.checkout, "switch", "-q", branch)
        else:
            git.must(self.checkout, "switch", "-q", "-c", branch)
            git.must(self.checkout, "config", f"branch.{branch}.base", current)

    def listener(self, item):
        on_line = self.on_line
        return None if on_line is None else lambda line: on_line(item.id, line)

    def pending(self):
        found = []
        for item in self.backlog.scan().valid.values():
            if item.workflow is None or item.id in self.failed:
                continue
            step = self.backlog.step(item)
            if step.automatic and not step.terminal:
                found.append((item, step))
        for stale in set(self.waiting) - {item.id for item, _ in found}:
            self.waiting.pop(stale, None)
            self.not_before.pop(stale, None)
        now = time.monotonic()
        return [(item, step) for item, step in found if self.not_before.get(item.id, now) <= now]

    def perform(self, item, step):
        """Perform one step and record its outcome; True when the item moved on."""
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        log = self.backlog.root / "log" / item.id / f"{step.name}-{stamp}.log"
        try:
            if step.uses_checkout(self):
                self.take_checkout(item)
            self.report(f"{item.id} {step.name}: started by {step.owner}")
            outcome, output = step.perform(self, item, log)
            updated = self.backlog.record(item.id, outcome, output, at=step.name)
        except Waiting as reason:
            if self.waiting.get(item.id) != str(reason):
                self.report(f"{item.id} {step.name}: {reason}")
            self.waiting[item.id] = str(reason)
            if step.retry_after:
                self.not_before[item.id] = time.monotonic() + step.retry_after
            return False
        except MovedOn as exc:
            self.waiting.pop(item.id, None)
            self.report(f"{item.id} {step.name}: {exc}; its {outcome!r} is not recorded")
            return True
        except Exception as exc:
            # One broken item must not stop the others, so anything unexpected fails just this item.
            reason = str(exc) if isinstance(exc, (StepFailed, InvalidStep, ValueError, OSError)) \
                else f"{type(exc).__name__}: {exc}"
            self.failed[item.id] = reason
            self.waiting.pop(item.id, None)
            self.report(f"{item.id} {step.name}: FAILED - {reason}; still at {step.name}, not retried until restart")
            return False
        self.waiting.pop(item.id, None)
        self.not_before.pop(item.id, None)
        self.report(f"{item.id} {step.name}: {outcome} -> {updated.step}")
        return True

    def run(self, once=False, interval=2.0, stop=None):
        stop = stop or threading.Event()
        while not stop.is_set():
            progressed = False
            for item, step in self.pending():
                if stop.is_set():
                    return
                progressed = self.perform(item, step) or progressed
            if once and not progressed:
                return
            if not progressed:
                stop.wait(interval)
