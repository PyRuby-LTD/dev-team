"""Runs automated steps: invoke the owning role, check or harness action, then apply its transition."""
import re
import threading
from concurrent.futures import Future
from datetime import datetime, timezone

from . import check as checks
from . import engines, git
from .backlog import InvalidRecord
from .config import ROOT, harness_command, load_roles
from .workflow import InvalidWorkflow
from .evidence import PathGuard

REPLY = re.compile(r"TRANSITION:\s*([A-Za-z0-9_-]+)\W*\Z")

PROTOCOL = """
## Work item

The work item is the file {{item}}. Read it first; it is the full context.
You may edit the body and set a valid `depends_on` list. Do not change any other front-matter field.
If it has a `## Feedback` section, the last entry there is the customer's reason
for sending the item to you; act on it.

## Run evidence

For `dev-team check`, cite the path the command prints: it has already saved
all output. Do not copy that output. Save any other command output you capture
under {{evidence_dir}} (the backlog's log/{{id}}/ directory).
Name checks and their results in the item without pasting output. Write paths
relative to the repository, and write the harness command as `dev-team`.

## Finishing

End your reply with a single line `TRANSITION: <name>`, where <name> is one of:

{{transitions}}
"""


class StepFailed(Exception):
    pass


class Waiting(Exception):
    pass


HARNESS_ACTIONS = {}


def render(step, values, workflow="default"):
    template = ROOT / "prompts" / workflow / f"{step.name}.md"
    if not template.is_file():
        template = ROOT / "prompts" / f"{step.name}.md"
    text = (template.read_text() if template.exists() else "") + PROTOCOL
    if "{{harness_command}}" in text:
        text = text.replace("{{harness_command}}", harness_command())
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


class Runner:
    def __init__(self, repository, roles=None, engine=engines.run, report=print, max_runs=16, checkout=None,
                 check=checks.run):
        self.repository = repository
        self.roles = load_roles() if roles is None else roles
        self.on_line = None
        self.engine = engine
        self.report = report
        self.max_runs = max_runs
        self.checkout = checkout
        self.check = check
        if repository.guard is None:
            repository.guard = PathGuard(checkout)
        repository.notice = lambda message: self.report(message)
        self.lock = threading.RLock()
        self._failed = {}
        self._waiting = {}
        self._active = set()
        self._runs = {}
        self.checkout_user = None
        self.on_change = None

    @property
    def failed(self):
        with self.lock:
            return dict(self._failed)

    @property
    def waiting(self):
        with self.lock:
            return dict(self._waiting)

    @property
    def runs(self):
        with self.lock:
            return dict(self._runs)

    @property
    def active(self):
        with self.lock:
            return set(self._active)

    def active_ids(self):
        with self.lock:
            return sorted(self._active)

    def uses_checkout(self, step):
        return (step.harness and step.action in {"merged", "abandon"}) or (
            step.role and self.roles[step.role].branch)

    def dependency_wait(self, record, step, snapshot):
        if not step.role or not self.roles[step.role].branch:
            return None
        dependencies = record.metadata.get("depends_on", [])
        if not dependencies or (self.checkout is not None and
                                git.has_ref(self.checkout, f"refs/heads/devteam/{record.id}")):
            return None
        valid = snapshot.valid
        unfinished = [valid[item_id] for item_id in dependencies
                      if valid[item_id].metadata["step"] != "done"]
        abandoned = [item.id for item in unfinished if item.metadata["step"] == "abandoned"]
        if abandoned:
            return f"blocked by abandoned {', '.join(abandoned)}; the customer must edit depends_on"
        if unfinished:
            names = ", ".join(f"{item.id} ({item.metadata['step']})" for item in unfinished)
            return f"waiting for {names} to be done"
        return None

    def checkout_holder(self, branch):
        if branch and branch.startswith("devteam/"):
            holder = self.repository.scan().valid.get(branch.removeprefix("devteam/"))
            if holder is not None and self.uses_checkout(self.repository.step(holder)):
                return holder
        return None

    def checkout_wait(self, record, branch):
        holder = self.checkout_holder(branch)
        if holder is not None and holder.id != record.id:
            return f"waiting for {holder.id}, which holds the checkout at step {holder.metadata['step']}"
        return None

    def claim(self, record, step):
        reason = None
        with self.lock:
            if record.id in self._active or record.id in self._failed:
                return False
            snapshot = self.repository.scan()
            current = snapshot.valid.get(record.id)
            if current is None or current.metadata != record.metadata:
                return False
            reason = self.dependency_wait(record, step, snapshot)
            if reason is None and self.uses_checkout(step):
                if self.checkout_user is not None:
                    reason = f"waiting for {self.checkout_user}, which is using the checkout"
                else:
                    if self.checkout is not None:
                        reason = self.checkout_wait(record, git.current_branch(self.checkout))
                    if reason is None:
                        self.checkout_user = record.id
            if reason is None:
                self._waiting.pop(record.id, None)
                self._active.add(record.id)
                return True
        self.note_waiting(record, step, reason)
        return False

    def note_waiting(self, record, step, reason):
        with self.lock:
            changed = self._waiting.get(record.id) != str(reason)
            self._waiting[record.id] = str(reason)
        if changed:
            self.report(f"{record.id} {step.name}: {reason}")

    def pending(self):
        found = []
        for record in self.repository.scan().valid.values():
            if record.metadata["type"] == "epic" or record.id in self.failed or record.id in self.active:
                continue
            step = self.repository.step(record)
            if step.role or step.harness:
                found.append((record, step))
        return found

    def switch_branch(self, item_id):
        """Switch to existing work for manual inspection after agents have stopped."""
        with self.lock:
            if self._active:
                raise Waiting("Wait for the running steps to finish before switching branches.")
            if self.checkout is None:
                raise StepFailed("Switching branches needs a git repository.")
            if item_id not in self.repository.scan().valid:
                raise StepFailed("Select a valid work item first.")
            branch = f"devteam/{item_id}"
            if not git.has_ref(self.checkout, f"refs/heads/{branch}"):
                raise StepFailed(f"No existing branch for {item_id}.")
            if not git.clean(self.checkout):
                raise Waiting("The checkout has uncommitted changes; clean it before switching branches.")
            git.must(self.checkout, "switch", "-q", branch)
            return branch

    def take_checkout(self, record):
        """Put the checkout on the item's branch, preserving another checkout step's place."""
        if self.checkout is None:
            raise StepFailed("this role works on a branch, which needs a git repository")
        branch = f"devteam/{record.id}"
        current = git.current_branch(self.checkout)
        if current == branch:
            return branch
        if current is None:
            raise StepFailed("the checkout is not on a branch")
        reason = self.checkout_wait(record, current)
        if reason is not None:
            raise Waiting(reason)
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
        workflow = self.repository.workflow(record.metadata["workflow"])
        check_names = [candidate.name for candidate in workflow.steps.values() if candidate.check]
        evidence = root / "log" / record.id
        logs = sorted((path for name in check_names for path in evidence.glob(f"{name}-*.log")),
                      key=lambda path: path.name.rsplit("-", 1)[-1])
        values = {
            "evidence_dir": str(evidence),
            "verify_log": str(logs[-1]) if logs else "No workflow check has run yet.",
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
        self.count_run(record)
        if role.push:
            git.push_branch(self.checkout, branch)
        log.parent.mkdir(parents=True, exist_ok=True)
        self.report(f"{record.id} {step.name}: {role.name} started")
        listener = self.on_line
        options = {"on_line": lambda line: listener(record.id, line)} if listener is not None else {}
        code, reply = self.engine(role, render(step, values, record.metadata["workflow"]),
                                  self.checkout or root, root, log, **options)
        if code != 0:
            raise StepFailed(f"exit {code}")
        lines = reply.strip().splitlines()
        match = REPLY.search(lines[-1]) if lines else None
        if match is None:
            raise StepFailed("the reply did not end with a TRANSITION line")
        if match.group(1) not in step.transitions:
            raise StepFailed(f"the reply named {match.group(1)!r}, which is not a transition from {step.name!r}")
        current = self.repository.scan().valid.get(record.id)
        if current is None or ({k: v for k, v in current.metadata.items() if k != "depends_on"} !=
                               {k: v for k, v in record.metadata.items() if k != "depends_on"}):
            raise StepFailed("the agent changed or broke the item's front matter")
        # Agents often cannot write .git from their sandbox, so the runner commits their work.
        if role.branch and not git.clean(self.checkout):
            git.commit_all(self.checkout, f"{record.id}: {step.name} by {role.name}")
        return match.group(1), self.repository.transition(record.id, match.group(1))

    def count_run(self, record):
        # A revise loop between two agents would otherwise run unattended without limit.
        with self.lock:
            if self._runs.get(record.id, 0) >= self.max_runs:
                raise StepFailed(f"already ran {self.max_runs} steps this session")
            self._runs[record.id] = self._runs.get(record.id, 0) + 1

    def run_item(self, record, step, claimed=False):
        if not claimed and not self.claim(record, step):
            return False
        try:
            return self.perform_item(record, step)
        except Exception as exc:
            # Catch unexpected worker errors too; one broken item must not stop dispatch.
            with self.lock:
                self._failed[record.id] = str(exc)
            self.report(f"{record.id} {step.name}: FAILED - {type(exc).__name__}: {exc}; "
                        "not retried until restart")
            return True
        finally:
            with self.lock:
                self._active.discard(record.id)
                if self.checkout_user == record.id:
                    self.checkout_user = None
            if self.on_change is not None:
                try:
                    self.on_change()
                except Exception as exc:
                    with self.lock:
                        self._failed[record.id] = str(exc)
                    self.report(f"{record.id}: FAILED - state listener: {exc}; not retried until restart")

    def perform_item(self, record, step):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        log = self.repository.root / "log" / record.id / f"{step.name}-{stamp}.log"
        if step.harness:
            label = f"{record.id} {step.name} (harness: {step.action})"
        else:
            role = self.roles[step.role]
            label = f"{record.id} {step.name} ({role.name} via {role.engine}/{role.model})"
        try:
            if step.harness:
                name = HARNESS_ACTIONS[step.action](self, record)
                updated = self.repository.transition(record.id, name)
            else:
                name, updated = self.invoke(record, step, log)
        except Waiting as reason:
            self.note_waiting(record, step, reason)
            return False
        except (StepFailed, git.GitError, InvalidRecord, InvalidWorkflow, OSError) as exc:
            with self.lock:
                self._failed[record.id] = str(exc)
            self.report(f"{label}: FAILED - {exc}; still at {step.name}, not retried until restart; see {log}")
            try:
                self.repository.commit(f"{record.id}: {step.name} failed", record.path)
            except InvalidRecord:
                pass
            return True
        with self.lock:
            self._waiting.pop(record.id, None)
        self.report(f"{label}: {name} -> {updated.metadata['step']}")
        return True

    def retry(self, item_id):
        with self.lock:
            self._failed.pop(item_id, None)
            self._runs.pop(item_id, None)

    def dispatch(self, stop=None):
        """Submit one step per runnable item, without joining workers or imposing a cap."""
        submitted = []
        for record, step in self.pending():
            if stop is not None and stop.is_set():
                break
            if not self.claim(record, step):
                continue
            future = Future()

            def work(record=record, step=step, future=future):
                future.set_result(self.run_item(record, step, claimed=True))

            threading.Thread(target=work, name=record.id, daemon=True).start()
            submitted.append(future)
        return submitted

    def run_pass(self):
        return sum(future.result() for future in self.dispatch())

    def run(self, once=False, interval=2.0, stop=None):
        """Poll for new work even while earlier steps are running; Stop only ends dispatch."""
        stop = stop if stop is not None else threading.Event()
        in_flight = []
        scan = True
        while not stop.is_set():
            if scan:
                in_flight.extend(self.dispatch(stop))
            completed = [future for future in in_flight if future.done()]
            progressed = sum(future.result() for future in completed) > 0
            in_flight = [future for future in in_flight if future not in completed]
            if once and not in_flight and not progressed:
                return
            # In once mode a waiting item is retried only after another step progresses.
            scan = not once or progressed
            if not progressed:
                stop.wait(min(interval, 0.05) if in_flight else interval)
