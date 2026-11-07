"""Workflow definitions: named steps, each with an owner and outcomes that lead to other steps."""
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import steps
from devteam.backlog import InvalidRecord, StrictLoader
from devteam.config import ROOT, load_roles

NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")
# The harness's own workflows, by name, once loaded in this process.
CACHE = {}


class InvalidWorkflow(ValueError):
    pass


@dataclass
class Workflow:
    name: str
    initial: str
    steps: dict


def build(name, data, roles, prompts=None, schemas=True):
    if not isinstance(data, dict) or set(data) != {"initial", "steps"}:
        raise InvalidWorkflow("a workflow has exactly 'initial' and 'steps'")
    if not isinstance(data["steps"], dict) or not data["steps"]:
        raise InvalidWorkflow("'steps' must map each step name to its definition")
    built = {}
    for step_name, spec in data["steps"].items():
        try:
            built[step_name] = steps.build(step_name, spec, roles, prompts, schemas)
        except steps.InvalidStep as exc:
            raise InvalidWorkflow(str(exc)) from None
    for step in built.values():
        for outcome in step.outcomes.values():
            if outcome.next not in built:
                raise InvalidWorkflow(f"step {step.name!r}: outcome {outcome.name!r} leads to "
                                      f"undefined step {outcome.next!r}")
    if data["initial"] not in built:
        raise InvalidWorkflow(f"initial step {data['initial']!r} is not defined")
    return Workflow(name, data["initial"], built)


def load(name, directory=None, roles=None, prompts=None, schemas=True):
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise InvalidWorkflow(f"invalid workflow name {name!r}")
    path = Path(directory or ROOT / "workflows") / f"{name}.yaml"
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=StrictLoader)
    except FileNotFoundError:
        raise InvalidWorkflow(f"workflow {name!r} is not defined ({path})") from None
    except (OSError, yaml.YAMLError, InvalidRecord) as exc:
        raise InvalidWorkflow(f"workflow {name!r}: {exc}") from None
    try:
        return build(name, data, load_roles().keys() if roles is None else roles, prompts, schemas)
    except InvalidWorkflow as exc:
        raise InvalidWorkflow(f"workflow {name!r}: {exc}") from None


def load_all(directory=None, roles=None, prompts=None):
    """Every workflow the harness defines, so a broken one is reported before anything runs."""
    own = directory is None and roles is None and prompts is None
    directory = Path(directory or ROOT / "workflows")
    loaded = {path.stem: load(path.stem, directory, roles, prompts) for path in sorted(directory.glob("*.yaml"))}
    if own:
        CACHE.update(loaded)
    return loaded


def cached(name):
    """One of the harness's own workflows, loaded once per process."""
    if name not in CACHE:
        CACHE[name] = load(name, schemas=False)
    return CACHE[name]
