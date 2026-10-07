"""Runs automated steps: invoke the owning role, check or harness action, then apply its transition."""
import json
import re
import subprocess
import time
from datetime import datetime, timezone

from . import check as checks
from . import engines, git, questions
from .backlog import InvalidRecord
from .config import ROOT, load_roles
from .workflow import InvalidWorkflow

REPLY = re.compile(r"TRANSITION:\s*([A-Za-z0-9_-]+)\W*\Z")
RECORDS = "docs/work-items"
GH_TIMEOUT = 60
PR_URL = re.compile(r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pull/([0-9]+)\b")

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


def rejected(runner, record):
    """Copy the PR's full submitted feedback before returning to implementation."""
    lines = record.body.splitlines()
    start = next((i for i, line in enumerate(lines)
                  if re.fullmatch(r"##\s+Pull request\s*", line, re.IGNORECASE)), None)
    urls = []
    if start is not None:
        end = next((i for i in range(start + 1, len(lines)) if questions.HEADING.match(lines[i])), len(lines))
        urls = PR_URL.findall("\n".join(lines[start + 1:end]))
    if not urls:
        raise StepFailed("PR URL is missing from ## Pull request (expected https://github.com/<owner>/<repo>/pull/<n>)")
    owner, repo, number = urls[-1]
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
        self.count_run(record)
        if role.record:
            copy = self.checkout / RECORDS / f"{record.id}.md"
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes(record.path.read_bytes())
            git.commit_all(self.checkout, f"{record.id}: record the work item", str(copy))
        if role.push:
            git.must(self.checkout, "push", "-q", "-u", "origin", branch)
        log.parent.mkdir(parents=True, exist_ok=True)
        self.active = record.id
        self.report(f"{record.id} {step.name}: {role.name} started")
        try:
            options = {"on_line": self.on_line} if self.on_line is not None else {}
            code, reply = self.engine(role, render(step, values, record.metadata["workflow"]),
                                      self.checkout or root, root, log, **options)
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

    def count_run(self, record):
        # A revise loop between two agents would otherwise run unattended without limit.
        if self.runs.get(record.id, 0) >= self.max_runs:
            raise StepFailed(f"already ran {self.max_runs} steps this session")
        self.runs[record.id] = self.runs.get(record.id, 0) + 1

    def verify(self, record, step, log):
        """Run the project's check on the item's branch; its exit code chooses the transition."""
        self.take_checkout(record)
        self.count_run(record)
        self.active = record.id
        self.report(f"{record.id} {step.name}: check started")
        try:
            code, output = self.check(self.checkout, log=log)
        finally:
            self.active = None
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        result = f"Run by the harness, {stamp}. Full output: `{log}`\n\n" + checks.summary(code, output, "the project check")
        current = self.repository.scan().valid.get(record.id)
        if current is None:
            raise StepFailed("the item is missing or invalid after the check")
        self.repository.write_body(record.id, questions.replace_section(current.body, "Test run", result), "test run")
        name = "passed" if code == 0 else "failed"
        return name, self.repository.transition(record.id, name)

    def run_item(self, record, step):
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
