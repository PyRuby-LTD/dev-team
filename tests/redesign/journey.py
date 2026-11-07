"""Journeys through the dev-team commands, with a scripted engine standing in for every agent.

The scripted engine runs in the harness's own process. Each time the harness invokes an agent, the engine takes the
next turn from the test's script and runs it with an Agent: the item and prompt the agent was given, the checkout it
works in, and the dev-team commands it may call, as a real agent would through the command line.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from devteam.redesign.commands import CommandFailed, DevTeam
from devteam.redesign.work_item import load

ROOT = Path(__file__).resolve().parents[2]
GIT = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
       "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


class Agent:
    """One invocation of an agent: what it was given, what it saw on starting, and the commands it can call."""

    def __init__(self, team, role, item_id, prompt, cwd):
        self.team = team
        self.role = role
        self.item_id = item_id
        self.prompt = prompt
        self.cwd = Path(cwd)
        self.item = team.backlog().get(item_id)
        self.branch = git("branch", "--show-current", cwd=cwd).strip()
        self.refusals = []

    @property
    def engine(self):
        return self.role.engine

    def write(self, name, text):
        (self.cwd / name).write_text(text)

    def submit(self, outcome, output=""):
        self.team.submit(self.item_id, outcome, output)

    def attempt(self, outcome, output=""):
        """Submit, keeping the reason when the submission is refused."""
        try:
            self.submit(outcome, output)
        except CommandFailed as exc:
            self.refusals.append(str(exc))

    def create(self, kind, title, fields=""):
        return self.team.create(kind, title, fields)

    def update(self, item_id, fields):
        return self.team.update(item_id, fields)


def submit(outcome, output=""):
    return lambda agent: agent.submit(outcome, output)


def then(*turns):
    """One turn made of several; the first exit code any of them gives is the turn's."""
    def turn(agent):
        for each in turns:
            code = each(agent)
            if code is not None:
                return code
    return turn


def nothing(agent):
    """An agent that exits without submitting anything."""


class Scripted:
    """The engine: each invocation takes the next turn, from one script or from the script for its item's title."""

    def __init__(self):
        self.team = None
        self.script = []
        self.agents = []
        self.lock = threading.Lock()

    def plan(self, *turns):
        self.script = list(turns)

    def plan_by_title(self, scripts):
        self.script = {word: list(turns) for word, turns in scripts.items()}

    def next_turn(self, agent):
        with self.lock:
            self.agents.append(agent)
            script = self.script
            if isinstance(script, dict):
                script = next((turns for word, turns in script.items() if word in agent.item.title), [])
            return script.pop(0) if script else None

    def __call__(self, role, prompt, cwd, extra_dir, log, *, on_line=None):
        agent = Agent(self.team, role, log.parent.name, prompt, cwd)
        turn = self.next_turn(agent)
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(prompt)
        if turn is None:
            return 97, ""
        code = turn(agent)
        return code or 0, ""


class Product(unittest.TestCase):
    """A product with a GitHub origin, set up for dev-team, whose agents follow the test's script."""

    def setUp(self):
        self.base = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.enterContext(patch.dict(os.environ, GIT))
        self.product = self.base / "product"
        self.product.mkdir()
        self.git("init", "-q", "-b", "main")
        (self.product / "README.md").write_text("A meal planner.\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "Start")
        self.git("remote", "add", "origin", "git@github.com:o/meals.git")
        self.agent = Scripted()
        self.reports = []
        self.team = self.dev_team(self.product)
        self.set_up_product()

    def dev_team(self, product, **kwargs):
        team = DevTeam(product, **{"engine": self.agent, "report": self.reports.append, **kwargs})
        self.agent.team = team
        return team

    def set_up_product(self):
        (self.product / "Makefile").write_text("regression:\n\ttrue\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "Add a regression target")
        self.team.init()

    def git(self, *args, cwd=None):
        return git(*args, cwd=cwd or self.product)

    def script(self, *turns):
        self.agent.plan(*turns)

    def run_once(self):
        failed = self.team.run(once=True)
        self.assertEqual({}, failed, "\n".join(self.reports))

    def run_failing(self):
        failed = self.team.run(once=True)
        self.assertTrue(failed, "every step succeeded")
        return failed

    def refused(self, command, *args):
        with self.assertRaises(CommandFailed) as refusal:
            command(*args)
        return str(refusal.exception)

    def seen(self, number):
        """The agent invoked at the given count, from one, as it started."""
        return self.agent.agents[number - 1]

    def seen_at(self, step):
        """The item as the agent last started at the given step saw it."""
        return [agent for agent in self.agent.agents if agent.item.step == step][-1].item

    def previewable(self, step, item_id):
        [prompt] = self.team.prompts(step, item=item_id)
        self.assertTrue(prompt.text.strip())

    def item(self, directory, item_id):
        return load(self.product / "backlog" / directory / f"{item_id}.yaml")

    def request(self):
        return self.item("requests", "REQUEST-001")

    def capture_and_analyse(self):
        self.team.create("request", "Plan meals", "overview: I want to plan a week of meals.\n")
        self.team.record("REQUEST-001", "analyse")
