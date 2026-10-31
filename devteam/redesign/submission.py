"""An agent's output for its step: checked when submitted, staged until the runner records it after the agent exits."""
import os
from pathlib import Path

import yaml

from devteam.backlog import InvalidRecord, StrictLoader

from .steps import AgentStep, InvalidStep


def parse(text):
    try:
        fragment = yaml.load(text, Loader=StrictLoader)
    except (yaml.YAMLError, InvalidRecord) as exc:
        raise InvalidStep(f"the output is not valid YAML: {exc}") from None
    return {} if fragment is None else fragment


def _path(root, item_id, step_name):
    return Path(root) / "log" / item_id / f"{step_name}.submission.yaml"


def stage(root, record, step, outcome, text):
    if not isinstance(step, AgentStep):
        raise InvalidStep(f"{record.id} is at step {step.name!r}, which is not an agent step")
    fragment = step.check(outcome, parse(text))
    path = _path(root, record.id, step.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(yaml.safe_dump({"outcome": outcome, "fragment": fragment}, sort_keys=False,
                                        allow_unicode=True), encoding="utf-8")
    os.replace(temporary, path)
    return path


def take(root, item_id, step_name):
    path = _path(root, item_id, step_name)
    try:
        staged = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    path.unlink()
    return staged["outcome"], staged["fragment"]
