"""The harness loop: perform each step the harness or an agent owns, then record its outcome and move the item on."""
from datetime import datetime, timezone
import threading

from devteam import check as checks
from devteam import engines
from devteam.config import load_roles

from .prompt import Prompts
from .steps import HumanStep, InvalidStep, StepFailed, Waiting


def record_customer(backlog, item_id, outcome, output):
    item = backlog.get(item_id)
    step = backlog.step(item)
    if not isinstance(step, HumanStep):
        raise InvalidStep(f"{item.id} is at step {step.name!r}, which {step.owner} performs, not the customer")
    return backlog.record(item.id, outcome, output)


class Harness:
    def __init__(self, backlog, checkout=None, roles=None, prompts=None, engine=engines.run, check=checks.run,
                 report=print):
        self.backlog = backlog
        self.checkout = checkout
        self.roles = load_roles() if roles is None else roles
        self.prompts = prompts or Prompts()
        self.engine = engine
        self.check = check
        self.report = report
        self.on_line = None
        self.failed = {}
        self.waiting = {}

    def values(self, item):
        return {"checkout": str(self.checkout or self.backlog.root),
                "evidence_dir": str(self.backlog.root / "log" / item.id)}

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
        return found

    def perform(self, item, step):
        """Perform one step and record its outcome; True when the item moved on."""
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        log = self.backlog.root / "log" / item.id / f"{step.name}-{stamp}.log"
        self.report(f"{item.id} {step.name}: started by {step.owner}")
        try:
            outcome, output = step.perform(self, item, log)
            updated = self.backlog.record(item.id, outcome, output)
        except Waiting as reason:
            if self.waiting.get(item.id) != str(reason):
                self.report(f"{item.id} {step.name}: {reason}")
            self.waiting[item.id] = str(reason)
            return False
        except Exception as exc:
            # One broken item must not stop the others, so anything unexpected fails just this item.
            reason = str(exc) if isinstance(exc, (StepFailed, InvalidStep, ValueError, OSError)) \
                else f"{type(exc).__name__}: {exc}"
            self.failed[item.id] = reason
            self.report(f"{item.id} {step.name}: FAILED - {reason}; still at {step.name}, not retried until restart")
            return False
        self.waiting.pop(item.id, None)
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
