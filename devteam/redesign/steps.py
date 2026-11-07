"""Workflow steps: the common interface the harness dispatches and the TUI displays, one class per kind of owner."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from devteam import check as checks
from devteam import engines, git
from devteam.config import ROOT

from . import github

# A step whose output is the item's requirements, merged into the item rather than kept beside it.
REQUIREMENTS = "requirements"
# The kinds of customer input the TUI knows; a customer step asking for anything else could never be answered.
CUSTOMER_INPUTS = ("questions", "feedback", "standards")


class InvalidStep(ValueError):
    pass


class StepFailed(Exception):
    """The step could not produce an outcome; the item stays where it is."""


class Waiting(Exception):
    """The step cannot run yet and is tried again later."""


@dataclass(frozen=True)
class Outcome:
    name: str
    next: str
    means: str


@dataclass
class Step:
    automatic: ClassVar[bool] = True
    produces: ClassVar[frozenset | None] = None
    retry_after: ClassVar[float | None] = None  # seconds before a waiting step is tried again

    name: str
    outcomes: dict
    output: dict | str | None = field(default=None, kw_only=True)  # a JSON Schema, REQUIREMENTS or nothing

    @property
    def owner(self):
        raise NotImplementedError

    @property
    def transitions(self):
        return {outcome.name: outcome.next for outcome in self.outcomes.values()}

    @property
    def terminal(self):
        return not self.outcomes

    @property
    def customer_outcomes(self):
        return {}

    @property
    def needs_you(self):
        return bool(self.customer_outcomes)

    def label(self):
        return "finished" if self.terminal else self.owner

    def uses_checkout(self, harness):
        return False

    def perform(self, harness, item, log):
        """Return the outcome's name and the output, or raise Waiting to be tried again later."""
        raise NotImplementedError(f"step {self.name!r} is not performed by the harness")

    def check(self, outcome, fragment):
        """The fragment, once the outcome is one of this step's and the fragment fits the step's output."""
        if outcome not in self.outcomes:
            valid = ", ".join(self.outcomes) or "none (terminal step)"
            raise InvalidStep(f"{outcome!r} is not an outcome of step {self.name!r}; valid: {valid}")
        fragment = {} if fragment is None else fragment
        if not isinstance(fragment, dict):
            raise InvalidStep(f"the output of step {self.name!r} must be a mapping")
        if "outcome" in fragment:
            raise InvalidStep(f"the output of step {self.name!r} must not set 'outcome'; the harness records it")
        if self.output is None:
            if fragment:
                raise InvalidStep(f"step {self.name!r} takes no output")
        elif self.output == REQUIREMENTS:
            from .work_item import InvalidWorkItem, check_requirements
            try:
                check_requirements(fragment)
            except InvalidWorkItem as exc:
                raise InvalidStep(f"the output of step {self.name!r} is not valid requirements: {exc}") from None
        else:
            errors = sorted(Draft202012Validator(self.output).iter_errors(fragment), key=lambda e: list(e.absolute_path))
            if errors:
                problems = "; ".join(f"{'.'.join(str(p) for p in e.absolute_path) or 'output'}: {e.message}"
                                     for e in errors)
                raise InvalidStep(f"the output of step {self.name!r} does not fit its schema: {problems}")
        return fragment

@dataclass
class HumanStep(Step):
    automatic: ClassVar[bool] = False

    @property
    def owner(self):
        return "human"

    @property
    def customer_outcomes(self):
        return self.outcomes

    def label(self):
        return "finished" if self.terminal else "YOU"


@dataclass
class AgentStep(Step):
    role: str
    prompt: Path

    @property
    def owner(self):
        return f"agent:{self.role}"

    def label(self):
        return "finished" if self.terminal else self.role

    def uses_checkout(self, harness):
        return harness.roles[self.role].branch

    def perform(self, harness, item, log):
        from . import submission

        role = harness.roles[self.role]
        root = harness.backlog.root
        if role.push:
            # Agents often cannot write .git from their sandbox, so the harness pushes the branch for them.
            try:
                git.push_branch(harness.checkout, f"devteam/{item.id}")
            except git.GitError as exc:
                raise StepFailed(f"could not push the branch for {role.name}: {exc}") from None
        prompt = harness.templates.prompt(item, self, harness.values(item), harness.backlog)
        # A submission left by an earlier run must not be taken for this one.
        submission.take(root, item.id, self.name)
        log.parent.mkdir(parents=True, exist_ok=True)
        try:
            code, _ = harness.engine(role, prompt, harness.checkout or root, root, log, on_line=harness.listener(item))
        except engines.EngineMissing as exc:
            raise StepFailed(str(exc)) from None
        if code != 0:
            submission.take(root, item.id, self.name)
            raise StepFailed(f"{role.command[0]} exited with code {code}; see {log}")
        staged = submission.take(root, item.id, self.name)
        if staged is None:
            raise StepFailed(f"{role.name} exited without submitting an outcome; see {log}")
        if role.branch:
            branch = f"devteam/{item.id}"
            if git.current_branch(harness.checkout) != branch:
                raise StepFailed(f"{role.name} left the checkout off {branch}; its work is not committed")
            outcome, _ = staged
            if git.merging(harness.checkout):
                self.end_merge(harness, item, outcome)
            else:
                # Agents often cannot write .git from their sandbox, so the harness commits their work.
                git.commit_all(harness.checkout, f"{item.id}: {self.name} by {role.name}")
        return staged

    def end_merge(self, harness, item, outcome):
        """Commit the merge an agent resolved, or abort it when the item lets go of the checkout."""
        following = harness.backlog.workflow(item.workflow).steps[self.outcomes[outcome].next]
        if not following.uses_checkout(harness):
            # The sync started from a clean checkout, so whatever the agent left belongs to the merge.
            git.abort_merge(harness.checkout)
            return
        conflicts = [name for entry in item.pending(self.name) for name in entry.output.get("conflicts", [])]
        try:
            git.finish_merge(harness.checkout, conflicts)
        except git.GitError as exc:
            raise StepFailed(f"the merge is not resolved: {exc}") from None


def published(item):
    """The number of the pull request the item was last published as."""
    for entry in reversed(item.step_outputs):
        if isinstance(entry.output.get("pull_request"), int):
            return entry.output["pull_request"]
    raise StepFailed(f"no pull request is recorded for {item.id}")


def _github(lookup, harness, item):
    if harness.checkout is None:
        raise StepFailed("looking up the pull request needs a git repository")
    try:
        return lookup(harness.checkout, published(item))
    except github.GitHubError as exc:
        raise StepFailed(str(exc)) from None


@dataclass
class HarnessStep(Step):
    kind: ClassVar[str] = "harness"

    @property
    def owner(self):
        cls = type(self)
        name = cls.__name__ if cls.__module__ == __name__ else f"{cls.__module__}.{cls.__name__}"
        return f"{self.kind}:{name}"

    @property
    def customer_outcomes(self):
        # The workflow may give a harness step outcomes it never produces, such as abandoning a pull request.
        return {name: outcome for name, outcome in self.outcomes.items() if name not in self.produces}

    def label(self):
        return "finished" if self.terminal else self.kind


@dataclass
class Check(HarnessStep):
    produces: ClassVar[frozenset] = frozenset({"passed", "failed"})

    def uses_checkout(self, harness):
        return True

    def perform(self, harness, item, log):
        if harness.checkout is None:
            raise StepFailed("the check needs a git repository")
        result = harness.check(harness.checkout, log=log)
        code, output = result
        passed = code == 0 and result.status == "finished"
        verdict = f"exit {code}" if result.status == "finished" else result.status
        return ("passed" if passed else "failed"), {"summary": f"{verdict}\n{checks.tail(output)}"}


@dataclass
class Rejected(HarnessStep):
    produces: ClassVar[frozenset] = frozenset({"completed"})

    def perform(self, harness, item, log):
        comments = _github(github.comments, harness, item)
        return "completed", {"pull_request": published(item), "comments": comments}


@dataclass
class GitStep(HarnessStep):
    kind: ClassVar[str] = "git"

    def uses_checkout(self, harness):
        return True

    def clean_branch(self, harness, item):
        branch = f"devteam/{item.id}"
        base = git.base_of(harness.checkout, branch)
        if base is None:
            raise StepFailed(f"no base branch is recorded for {branch}")
        if not git.clean(harness.checkout):
            raise StepFailed(f"the checkout has uncommitted changes on {branch}")
        return branch, base


@dataclass
class Sync(GitStep):
    produces: ClassVar[frozenset] = frozenset({"completed", "conflicted"})

    def perform(self, harness, item, log):
        branch, base = self.clean_branch(harness, item)
        try:
            outcome = git.sync_branch(harness.checkout, branch, base)
        except git.GitError as exc:
            raise StepFailed(str(exc)) from None
        if outcome == "conflicted":
            return outcome, {"conflicts": [name for name in git.conflicted_files(harness.checkout) if name]}
        return outcome, {}


@dataclass
class Merged(GitStep):
    produces: ClassVar[frozenset] = frozenset({"completed"})

    def perform(self, harness, item, log):
        _, base = self.clean_branch(harness, item)
        try:
            git.fetch(harness.checkout, "origin")
            git.fast_forward(harness.checkout, base, f"origin/{base}")
        except git.GitError as exc:
            raise StepFailed(str(exc)) from None
        return "completed", {}


@dataclass
class Abandon(GitStep):
    produces: ClassVar[frozenset] = frozenset({"completed"})

    def perform(self, harness, item, log):
        _, base = self.clean_branch(harness, item)
        git.must(harness.checkout, "switch", "-q", base)
        return "completed", {}


@dataclass
class PullRequest(GitStep):
    produces: ClassVar[frozenset] = frozenset({"merged"})
    retry_after: ClassVar[float] = 60

    def uses_checkout(self, harness):
        return False

    def perform(self, harness, item, log):
        state = _github(github.state, harness, item)
        if state == "MERGED":
            return "merged", {}
        choices = " or ".join(f"'{name}'" for name in self.customer_outcomes)
        raise Waiting(f"pull request #{published(item)} is {state.lower()}"
                      + (f"; it moves on when merged, or when you choose {choices}" if choices else ""))


def _outcomes(step_name, spec):
    if not isinstance(spec, dict):
        raise InvalidStep(f"step {step_name!r}: outcomes must map each name to 'next' and 'means'")
    outcomes = {}
    for name, option in spec.items():
        if not isinstance(option, dict) or set(option) != {"next", "means"}:
            raise InvalidStep(f"step {step_name!r}: outcome {name!r} must have exactly 'next' and 'means'")
        if not isinstance(option["next"], str) or not option["next"]:
            raise InvalidStep(f"step {step_name!r}: outcome {name!r} must name the next step")
        if not isinstance(option["means"], str) or not option["means"].strip():
            raise InvalidStep(f"step {step_name!r}: outcome {name!r} must say what it means")
        outcomes[name] = Outcome(name, option["next"], option["means"].strip())
    return outcomes


def _prompt(step_name, name, prompts):
    directory = Path(prompts or ROOT / "prompts").resolve()
    if not isinstance(name, str) or not name:
        raise InvalidStep(f"step {step_name!r}: 'prompt' must name a file in {directory}")
    prompt = (directory / name).resolve()
    if not prompt.is_relative_to(directory):
        raise InvalidStep(f"step {step_name!r}: prompt {name!r} is outside {directory}")
    if not prompt.is_file():
        raise InvalidStep(f"step {step_name!r}: prompt {prompt} does not exist")
    return prompt


def _output(step_name, output, schemas):
    if output is None or output == REQUIREMENTS:
        return output
    if not isinstance(output, dict):
        raise InvalidStep(f"step {step_name!r}: 'output' must be {REQUIREMENTS!r} or a JSON Schema")
    if not schemas:
        return output
    try:
        Draft202012Validator.check_schema(output)
    except SchemaError as exc:
        raise InvalidStep(f"step {step_name!r}: 'output' is not a valid JSON Schema: {exc.message}") from None
    return output


def _harness_step(step_name, owner):
    kind, _, name = owner.partition(":")
    module, _, class_name = name.rpartition(".")
    if module:
        raise InvalidStep(f"step {step_name!r}: steps from {module!r} are not supported yet")
    cls = globals().get(class_name)
    # A grouping such as GitStep produces nothing, so it cannot be a step itself.
    if not (isinstance(cls, type) and issubclass(cls, HarnessStep) and cls.produces is not None):
        raise InvalidStep(f"step {step_name!r}: {class_name!r} is not a harness step in {__name__}")
    if cls.kind != kind:
        raise InvalidStep(f"step {step_name!r}: {class_name} is a {cls.kind} step, so its owner is "
                          f"'{cls.kind}:{class_name}'")
    return cls


def build(step_name, spec, roles, prompts=None, schemas=True):
    """One step from its workflow definition; whether each outcome's next step exists is the workflow's concern.

    Checking output schemas against the JSON Schema metaschema is most of the cost of loading a workflow, so
    schemas=False skips it where launch has already checked them.
    """
    if not isinstance(spec, dict) or "owner" not in spec:
        raise InvalidStep(f"step {step_name!r} must have an 'owner'")
    owner = spec["owner"]
    agent = isinstance(owner, str) and owner.startswith("agent:")
    if owner != "human" and not agent and not (isinstance(owner, str) and owner.startswith(("harness:", "git:"))):
        raise InvalidStep(f"step {step_name!r}: owner must be 'human', 'agent:<role>', "
                          "'harness:<class>' or 'git:<class>'")
    expected = {"owner", "prompt", "outcomes"} if agent else {"owner", "outcomes"}
    if set(spec) - {"output"} != expected:
        raise InvalidStep(f"step {step_name!r} owned by {owner!r} must have exactly "
                          + ", ".join(repr(key) for key in sorted(expected)) + ", and may have 'output'")
    outcomes = _outcomes(step_name, spec["outcomes"])
    output = _output(step_name, spec.get("output"), schemas)
    if owner == "human":
        if isinstance(output, dict):
            if unknown := [name for name in output.get("properties", {}) if name not in CUSTOMER_INPUTS]:
                raise InvalidStep(f"step {step_name!r}: the customer has no way to enter "
                                  + ", ".join(repr(name) for name in unknown)
                                  + "; a customer step's output may only have " + ", ".join(CUSTOMER_INPUTS))
        return HumanStep(step_name, outcomes, output=output)
    if not agent:
        action = _harness_step(step_name, owner)
        # The customer may add outcomes of their own, such as abandoning a pull request.
        if missing := action.produces - set(outcomes):
            raise InvalidStep(f"step {step_name!r}: {action.__name__} needs the outcomes "
                              + ", ".join(repr(name) for name in sorted(missing)))
        return action(step_name, outcomes, output=output)
    role = owner.removeprefix("agent:")
    if role not in roles:
        raise InvalidStep(f"step {step_name!r}: role {role!r} is not in config/roles.toml")
    return AgentStep(step_name, outcomes, role, _prompt(step_name, spec["prompt"], prompts), output=output)
