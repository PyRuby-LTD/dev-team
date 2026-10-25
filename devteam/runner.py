"""Runs automated steps: invoke the owning role, check or harness action, then apply its transition."""
import json
import re
import subprocess
import time
import threading
from concurrent.futures import Future
from datetime import datetime, timezone

from . import check as checks
from . import engines, git, questions
from .backlog import InvalidRecord, mutation
from .config import ROOT, harness_command, load_roles
from .workflow import InvalidWorkflow
from .evidence import PathGuard

REPLY = re.compile(r"TRANSITION:\s*([A-Za-z0-9_-]+)\W*\Z")
RECORDS = "docs/work-items"
GH_TIMEOUT = 60
PR_POLL_SECONDS = 60
PR_URL = re.compile(r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pull/([0-9]+)\b")

PROTOCOL = """
## Work item

The work item is the file {{item}}. Read it first; it is the full context.
You may edit the body of that file. Do not change its front matter.
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


def merged(runner, record):
    """Bring the recorded base up to date after the customer's merge decision."""
    if runner.checkout is None:
        raise StepFailed("the merged step needs a git repository")
    branch = f"devteam/{record.id}"
    base = git.base_of(runner.checkout, branch)
    if base is None:
        raise StepFailed(f"no base branch is recorded for {branch}")
    if not git.clean(runner.checkout):
        current = git.current_branch(runner.checkout)
        raise StepFailed(f"the checkout has uncommitted changes on {current}")
    git.fetch(runner.checkout, "origin")
    git.fast_forward(runner.checkout, base, f"origin/{base}")
    return "completed"


def pull_request(record):
    """Use the last PR URL in the publisher's section, excluding later feedback."""
    lines = record.body.splitlines()
    start = next((i for i, line in enumerate(lines)
                  if re.fullmatch(r"##\s+Pull request\s*", line, re.IGNORECASE)), None)
    urls = []
    if start is not None:
        end = next((i for i in range(start + 1, len(lines)) if questions.HEADING.match(lines[i])), len(lines))
        urls = PR_URL.findall("\n".join(lines[start + 1:end]))
    if not urls:
        raise StepFailed("PR URL is missing from ## Pull request (expected https://github.com/<owner>/<repo>/pull/<n>)")
    return urls[-1]


def pr_state(record):
    owner, repo, number = pull_request(record)
    argv = ["gh", "pr", "view", f"https://github.com/{owner}/{repo}/pull/{number}", "--json", "state"]
    call = " ".join(argv)
    try:
        result = subprocess.run(argv, capture_output=True, text=True, errors="replace", timeout=GH_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise StepFailed(f"{call}: timed out after {GH_TIMEOUT} seconds") from exc
    if result.returncode:
        raise StepFailed(f"{call}: exit {result.returncode}: {result.stderr.strip()}")
    try:
        data = json.loads(result.stdout)
        if not isinstance(data, dict) or data.get("state") not in ("OPEN", "CLOSED", "MERGED"):
            raise ValueError("expected state OPEN, CLOSED or MERGED")
    except ValueError as exc:
        raise StepFailed(f"{call}: invalid JSON response: {exc}") from exc
    return data["state"]


def rejected(runner, record):
    """Copy the PR's full submitted feedback before returning to implementation."""
    owner, repo, number = pull_request(record)
    base = f"repos/{owner}/{repo}"
    reviews = pr_comments(f"{base}/pulls/{number}/reviews")
    inline = pr_comments(f"{base}/pulls/{number}/comments")
    conversation = pr_comments(f"{base}/issues/{number}/comments")
    feedback = render_pr_feedback(reviews, inline, conversation)
    runner.repository.write_body(record.id, questions.replace_section(record.body, "Pull request feedback", feedback),
                                 "pull request feedback")
    return "completed"


def pr_comments(endpoint):
    """gh pagination prints consecutive JSON arrays; accept only arrays of objects."""
    argv = ["gh", "api", endpoint, "--paginate"]
    call = " ".join(argv)
    try:
        result = subprocess.run(argv, capture_output=True, text=True, errors="replace", timeout=GH_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise StepFailed(f"{call}: timed out after {GH_TIMEOUT} seconds") from exc
    if result.returncode:
        raise StepFailed(f"{call}: exit {result.returncode}: {result.stderr.strip()}")
    decoder = json.JSONDecoder()
    remaining, comments = result.stdout.strip(), []
    try:
        if not remaining:
            raise ValueError("empty output")
        while remaining:
            page, end = decoder.raw_decode(remaining)
            if not isinstance(page, list) or any(not isinstance(entry, dict) for entry in page):
                raise ValueError("expected an array of objects")
            if any(entry.get("body") is not None and not isinstance(entry["body"], str) for entry in page):
                raise ValueError("expected comment bodies to be strings")
            comments.extend(page)
            remaining = remaining[end:].lstrip()
    except ValueError as exc:
        raise StepFailed(f"{call}: invalid JSON response: {exc}") from exc
    return comments


def render_pr_feedback(reviews, inline, conversation):
    def field(value):
        # Keep metadata on its introduction line too, even in malformed API data.
        return " ".join(str(value).splitlines()) if value is not None else ""

    entries = []

    def add(kind, comment, date, location=""):
        user = comment.get("user")
        author = field(user.get("login")) if isinstance(user, dict) else ""
        title = f"**{kind}** by {author or 'unknown author'}{location}"
        stamp = field(comment.get(date))
        if stamp:
            title += f" ({stamp})"
        body = comment.get("body") or ""
        entries.append(title + ":\n" + "\n".join("> " + line for line in body.splitlines()))

    for review in reviews:
        if review.get("state") == "PENDING" or not review.get("submitted_at") or not review.get("body"):
            continue
        add(f"Review ({field(review.get('state'))})", review, "submitted_at")
    for comment in inline:
        location = f" on {field(comment.get('path'))}"
        if comment.get("subject_type") != "file":
            if comment.get("line") is not None:
                location += f" line {field(comment['line'])}"
            elif comment.get("original_line") is not None:
                location += f" line {field(comment['original_line'])} (outdated)"
        add("Inline comment", comment, "created_at", location)
    for comment in conversation:
        add("Conversation comment", comment, "created_at")
    return "\n\n".join(entries) if entries else "There are no comments on this pull request."


HARNESS_ACTIONS = {"merged": merged, "rejected": rejected}


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
        self._pr_started = {}
        self._pr_lookups = {}
        self._pr_problems = {}
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
        return step.check or (step.harness and step.action == "merged") or (
            step.role and self.roles[step.role].branch)

    def claim(self, record, step):
        reason = None
        with self.lock:
            if record.id in self._active or record.id in self._failed:
                return False
            current = self.repository.scan().valid.get(record.id)
            if current is None or current.metadata != record.metadata:
                return False
            if self.uses_checkout(step):
                if self.checkout_user is not None:
                    reason = f"waiting for {self.checkout_user}, which is using the checkout"
                else:
                    self.checkout_user = record.id
            if reason is None:
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
            if step.role or step.check or step.harness:
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
        if role.record:
            copy = self.checkout / RECORDS / f"{record.id}.md"
            copy.parent.mkdir(parents=True, exist_ok=True)
            masked, numbers = self.repository.guard.mask(record.body)
            text = record.path.read_bytes().decode("utf-8")
            front = text[:len(text) - len(record.body)]
            copy.write_bytes((front + masked).encode("utf-8"))
            if numbers:
                offset = len(front.splitlines())
                self.report(f"{record.id}: copy masked lines {', '.join(str(offset + n) for n in numbers)}")
            git.commit_all(self.checkout, f"{record.id}: record the work item", str(copy))
        if role.push:
            git.must(self.checkout, "push", "-q", "-u", "origin", branch)
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
        if current is None or current.metadata != record.metadata:
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

    def verify(self, record, step, log):
        """Run the project's check on the item's branch; its exit code chooses the transition."""
        self.take_checkout(record)
        self.count_run(record)
        self.report(f"{record.id} {step.name}: check started")
        started = time.monotonic()
        outcome = self.check(self.checkout, log=log)
        code, _ = outcome
        duration = time.monotonic() - started
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        status = getattr(outcome, "status", "finished")
        verdict = status
        if status == "finished":
            verdict = ("passed" if code == 0 else "failed") + f" (exit {code})"
        result = f"Run by the harness, {stamp}: {verdict}; duration {duration:.3f} seconds.\n"
        current = self.repository.scan().valid.get(record.id)
        if current is None:
            raise StepFailed("the item is missing or invalid after the check")
        self.repository.write_body(record.id, questions.replace_section(current.body, "Test run", result), "test run")
        name = "passed" if code == 0 and status == "finished" else "failed"
        return name, self.repository.transition(record.id, name)

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
        if step.check:
            label = f"{record.id} {step.name} (check)"
        elif step.harness:
            label = f"{record.id} {step.name} (harness: {step.action})"
        else:
            role = self.roles[step.role]
            label = f"{record.id} {step.name} ({role.name} via {role.engine}/{role.model})"
        try:
            if step.check:
                name, updated = self.verify(record, step, log)
            elif step.harness:
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

    def poll_pull_requests(self):
        """Collect completed lookups and start due ones without waiting for GitHub."""
        for item_id, (record, future) in list(self._pr_lookups.items()):
            if not future.done():
                continue
            del self._pr_lookups[item_id]
            updated = None
            try:
                # The manual decision and this check/transition share the backlog lock.
                with mutation(self.repository.root):
                    current = self.repository.scan().valid.get(item_id)
                    if current != record or item_id in self.failed:
                        continue
                    state = future.result()
                    self._pr_problems.pop(item_id, None)
                    if state == "MERGED":
                        updated = self.repository.transition(item_id, "merged")
            except Exception as exc:
                problem = str(exc)
                if self._pr_problems.get(item_id) != problem:
                    self._pr_problems[item_id] = problem
                    self.report(f"{item_id} pull-request: {problem}")
            if updated is not None:
                self.report(f"{item_id} pull-request: merged -> {updated.metadata['step']}")
                if self.on_change is not None:
                    self.on_change()

        for record in self.repository.scan().valid.values():
            if record.metadata.get("step") != "pull-request" or record.id in self.failed:
                continue
            step = self.repository.step(record)
            if not step.human or "merged" not in step.transitions:
                continue
            now = time.monotonic()
            if record.id in self._pr_lookups or now - self._pr_started.get(record.id, -float("inf")) < PR_POLL_SECONDS:
                continue
            future = Future()
            self._pr_started[record.id] = now
            self._pr_lookups[record.id] = (record, future)

            def lookup(record=record, future=future):
                try:
                    future.set_result(pr_state(record))
                except Exception as exc:
                    future.set_exception(exc)

            threading.Thread(target=lookup, name=f"{record.id}-pr", daemon=True).start()

    def run(self, once=False, interval=2.0, stop=None):
        """Poll for new work even while earlier steps are running; Stop only ends dispatch."""
        stop = stop if stop is not None else threading.Event()
        in_flight = []
        scan = True
        while not stop.is_set():
            if not once:
                self.poll_pull_requests()
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
