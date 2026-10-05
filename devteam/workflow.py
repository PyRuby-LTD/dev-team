"""Workflow definitions: one owner per step and named transitions to other steps."""
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .config import ROOT, load_roles

CHECK = "check"
CHECK_OUTCOMES = {"passed", "failed"}
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")


class InvalidWorkflow(ValueError):
    pass


@dataclass
class Step:
    name: str
    owner: str
    transitions: dict

    @property
    def role(self):
        return self.owner.removeprefix("agent:") if self.owner.startswith("agent:") else None

    @property
    def human(self):
        return self.owner == "human"

    @property
    def check(self):
        return self.owner == CHECK

    @property
    def terminal(self):
        return not self.transitions


@dataclass
class Workflow:
    name: str
    initial: str
    steps: dict


def _unique(pairs):
    # json.loads keeps the last of two equal keys, which would silently drop a step.
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidWorkflow(f"duplicate key {key!r}")
        result[key] = value
    return result


def build(name, data, roles):
    if not isinstance(data, dict) or not isinstance(data.get("steps"), dict) or not data["steps"]:
        raise InvalidWorkflow("a workflow needs a nonempty 'steps' object")
    steps = {}
    for step_name, spec in data["steps"].items():
        if not isinstance(spec, dict) or set(spec) != {"owner", "transitions"}:
            raise InvalidWorkflow(f"step {step_name!r} must have exactly 'owner' and 'transitions'")
        owner, transitions = spec["owner"], spec["transitions"]
        if not isinstance(owner, str) or (owner not in ("human", CHECK) and not owner.startswith("agent:")):
            raise InvalidWorkflow(f"step {step_name!r}: owner must be 'human', 'agent:<role>' or 'check'")
        if owner.startswith("agent:") and owner.removeprefix("agent:") not in roles:
            raise InvalidWorkflow(f"step {step_name!r}: role {owner.removeprefix('agent:')!r} is not in config/roles.toml")
        if not isinstance(transitions, dict):
            raise InvalidWorkflow(f"step {step_name!r}: transitions must be an object of name -> step")
        for transition, target in transitions.items():
            if target not in data["steps"]:
                raise InvalidWorkflow(f"step {step_name!r}: transition {transition!r} targets undefined step {target!r}")
        if owner == CHECK and set(transitions) != CHECK_OUTCOMES:
            raise InvalidWorkflow(f"step {step_name!r}: a check step has exactly the transitions 'passed' and 'failed'")
        steps[step_name] = Step(step_name, owner, dict(transitions))
    if data.get("initial") not in steps:
        raise InvalidWorkflow(f"initial step {data.get('initial')!r} is not defined")
    if set(data) != {"initial", "steps"}:
        raise InvalidWorkflow("a workflow has only 'initial' and 'steps'")
    return Workflow(name, data["initial"], steps)


def load(name, directory=None, roles=None):
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise InvalidWorkflow(f"invalid workflow name {name!r}")
    path = Path(directory or ROOT / "workflows") / f"{name}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique)
    except FileNotFoundError:
        raise InvalidWorkflow(f"workflow {name!r} is not defined ({path})") from None
    except (OSError, ValueError) as exc:
        raise InvalidWorkflow(f"workflow {name!r}: {exc}") from exc
    try:
        return build(name, data, load_roles().keys() if roles is None else roles)
    except InvalidWorkflow as exc:
        raise InvalidWorkflow(f"workflow {name!r}: {exc}") from None
