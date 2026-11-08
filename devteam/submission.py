"""An agent's output for its step: checked when submitted, staged until the harness records it after the agent exits."""
import os
from pathlib import Path

from devteam.yaml_format import parse, to_yaml

from .steps import AgentStep, InvalidStep


def _path(root, item_id, step_name):
    return Path(root) / "log" / item_id / f"{step_name}.submission.yaml"


def stage(root, record, step, outcome, text):
    if not isinstance(step, AgentStep):
        raise InvalidStep(f"{record.id} is at step {step.name!r}, which is not an agent step")
    fragment = step.check(outcome, parse(text))
    path = _path(root, record.id, step.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(to_yaml({"outcome": outcome, "fragment": fragment}), encoding="utf-8")
    os.replace(temporary, path)
    return path


def take(root, item_id, step_name):
    path = _path(root, item_id, step_name)
    try:
        staged = parse(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    path.unlink()
    return staged["outcome"], staged["fragment"]
