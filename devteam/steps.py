"""Workflow steps: the common interface the runner dispatches and the TUI displays, one class per kind of owner."""
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from .config import ROOT


class InvalidStep(ValueError):
    pass


@dataclass(frozen=True)
class Outcome:
    name: str
    next: str
    means: str


@dataclass
class Step:
    automatic: ClassVar[bool] = True
    produces: ClassVar[frozenset | None] = None

    name: str
    outcomes: dict

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
    def needs_you(self):
        return not self.automatic and not self.terminal

    def label(self):
        return "finished" if self.terminal else self.owner

    def uses_checkout(self, runner):
        return False

    def perform(self, runner, record, log):
        """Return the outcome's name, or raise Waiting to be tried again later."""
        raise NotImplementedError(f"step {self.name!r} is not performed by the harness")


@dataclass
class HumanStep(Step):
    automatic: ClassVar[bool] = False

    @property
    def owner(self):
        return "human"

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

    def uses_checkout(self, runner):
        return runner.roles[self.role].branch

    def perform(self, runner, record, log):
        # invoke still applies the transition itself; that moves to the runner when steps are integrated.
        name, _ = runner.invoke(record, self, log)
        return name


def _actions():
    # The actions still live in the runner, which will import this module once steps are integrated.
    from . import runner
    return runner


@dataclass
class HarnessStep(Step):
    kind: ClassVar[str] = "harness"

    @property
    def owner(self):
        cls = type(self)
        name = cls.__name__ if cls.__module__ == __name__ else f"{cls.__module__}.{cls.__name__}"
        return f"{self.kind}:{name}"

    def label(self):
        return "finished" if self.terminal else self.kind


@dataclass
class Check(HarnessStep):
    produces: ClassVar[frozenset] = frozenset({"passed", "failed"})

    def uses_checkout(self, runner):
        return True

    def perform(self, runner, record, log):
        # verify still applies the transition itself, as invoke does.
        name, _ = runner.verify(record, self, log)
        return name


@dataclass
class Rejected(HarnessStep):
    produces: ClassVar[frozenset] = frozenset({"completed"})

    def perform(self, runner, record, log):
        return _actions().rejected(runner, record)


@dataclass
class GitStep(HarnessStep):
    kind: ClassVar[str] = "git"

    def uses_checkout(self, runner):
        return True


@dataclass
class Sync(GitStep):
    produces: ClassVar[frozenset] = frozenset({"completed", "conflicted"})

    def perform(self, runner, record, log):
        return _actions().sync(runner, record)


@dataclass
class Merged(GitStep):
    produces: ClassVar[frozenset] = frozenset({"completed"})

    def perform(self, runner, record, log):
        return _actions().merged(runner, record)


@dataclass
class Abandon(GitStep):
    produces: ClassVar[frozenset] = frozenset({"completed"})

    def perform(self, runner, record, log):
        return _actions().abandon(runner, record)


@dataclass
class PullRequest(GitStep):
    produces: ClassVar[frozenset] = frozenset({"merged"})
    retry_after: ClassVar[float] = 60

    def uses_checkout(self, runner):
        return False

    def perform(self, runner, record, log):
        actions = _actions()
        state = actions.pr_state(record)
        if state == "MERGED":
            return "merged"
        raise actions.Waiting(f"the pull request is {state.lower()}")


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


def build(step_name, spec, roles, prompts=None):
    """One step from its workflow definition; whether each outcome's next step exists is the workflow's concern."""
    if not isinstance(spec, dict) or "owner" not in spec:
        raise InvalidStep(f"step {step_name!r} must have an 'owner'")
    owner = spec["owner"]
    agent = isinstance(owner, str) and owner.startswith("agent:")
    if owner != "human" and not agent and not (isinstance(owner, str) and owner.startswith(("harness:", "git:"))):
        raise InvalidStep(f"step {step_name!r}: owner must be 'human', 'agent:<role>', "
                          "'harness:<class>' or 'git:<class>'")
    expected = {"owner", "prompt", "outcomes"} if agent else {"owner", "outcomes"}
    if set(spec) != expected:
        raise InvalidStep(f"step {step_name!r} owned by {owner!r} must have exactly "
                          + ", ".join(repr(key) for key in sorted(expected)))
    outcomes = _outcomes(step_name, spec["outcomes"])
    if owner == "human":
        return HumanStep(step_name, outcomes)
    if not agent:
        action = _harness_step(step_name, owner)
        # The customer may add outcomes of their own, such as abandoning a pull request.
        if missing := action.produces - set(outcomes):
            raise InvalidStep(f"step {step_name!r}: {action.__name__} needs the outcomes "
                              + ", ".join(repr(name) for name in sorted(missing)))
        return action(step_name, outcomes)
    role = owner.removeprefix("agent:")
    if role not in roles:
        raise InvalidStep(f"step {step_name!r}: role {role!r} is not in config/roles.toml")
    return AgentStep(step_name, outcomes, role, _prompt(step_name, spec["prompt"], prompts))
