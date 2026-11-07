"""The request workflow driven through the dev-team command, with stub engines following a scripted plan."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

from devteam.redesign.work_item import load

ROOT = Path(__file__).resolve().parents[2]
SCRIPTED = ROOT / "tests" / "stubs" / "scripted"
DEV_TEAM = f"{sys.executable} -P -m devteam"
GIT = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
       "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
TOOLS = ("git", "sh", "env", "python3")

QUESTIONS = """$DEV_TEAM backlog submit REQUEST-001 questions <<'OUTPUT'
questions:
  - question: Who plans the meals?
OUTPUT
"""

DRAFTS = """$DEV_TEAM backlog submit REQUEST-001 divided <<'OUTPUT'
work_items: [EPIC-001]
OUTPUT
echo "refused=$?"
$DEV_TEAM backlog create epic "Meal planning" <<'ITEM'
overview: Plan a week of meals.
ITEM
$DEV_TEAM backlog create story "Plan a week" <<'ITEM'
parent: EPIC-001
overview: As a cook, I want to plan a week of meals.
ITEM
$DEV_TEAM backlog submit REQUEST-001 drafted <<'OUTPUT'
work_items: [EPIC-001, STORY-001]
OUTPUT
"""


class Product(unittest.TestCase):
    def setUp(self):
        self.base = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.product = self.base / "product"
        self.product.mkdir()
        self.git("init", "-q", "-b", "main")
        (self.product / "README.md").write_text("A meal planner.\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "Start")
        self.prompts = self.base / "prompts"
        self.plan = self.base / "plan.json"
        self.bin = self.base / "bin"
        self.bin.mkdir()
        for tool in TOOLS:
            (self.bin / tool).symlink_to(shutil.which(tool))
        self.engines()

    def engines(self, *names):
        for name in names or ("claude", "codex"):
            shutil.copy(SCRIPTED, self.bin / name)
            (self.bin / name).chmod(0o755)

    def git(self, *args, cwd=None):
        return subprocess.run(["git", *args], cwd=cwd or self.product, env={**os.environ, **GIT},
                              capture_output=True, text=True, check=True).stdout

    def dev_team(self, *args, stdin="", command=DEV_TEAM, env=None):
        environment = {**os.environ, **GIT, "PATH": str(self.bin), "DEV_TEAM": DEV_TEAM,
                       "STUB_PLAN": str(self.plan), "STUB_PROMPTS": str(self.prompts), **(env or {})}
        return subprocess.run([*command.split(), *args], cwd=self.product, env=environment, input=stdin,
                              capture_output=True, text=True, timeout=120)

    def ok(self, *args, stdin=""):
        result = self.dev_team(*args, stdin=stdin)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        return result

    def script(self, *entries):
        self.plan.write_text(json.dumps(list(entries)))

    def item(self, directory, item_id):
        return load(self.product / "backlog" / directory / f"{item_id}.yaml")

    def request(self):
        return self.item("requests", "REQUEST-001")

    def capture_and_analyse(self):
        self.ok("backlog", "create", "request", "Plan meals", stdin="overview: I want to plan a week of meals.\n")
        self.ok("backlog", "record", "REQUEST-001", "analyse")


class RequestJourney(Product):
    def test_a_request_is_analysed_into_a_question_answered_and_divided_into_drafts(self):
        self.script({"sh": QUESTIONS}, {"sh": DRAFTS})
        self.capture_and_analyse()
        self.assertEqual("analysis", self.request().step)

        self.ok("run", "--once")
        self.assertEqual("answering", self.request().step)
        self.assertEqual(["Who plans the meals?"], [q.question for q in self.request().questions])

        self.ok("backlog", "record", "REQUEST-001", "answered",
                stdin="questions:\n  - question: Who plans the meals?\n    answer: The household cook.\n")
        self.assertEqual("analysis", self.request().step)

        self.ok("run", "--once")
        shell = (self.prompts / "02-claude.out").read_text()
        self.assertIn("refused=1", shell)
        self.assertGreater(len(shell.replace("refused=1", "").strip()), 0, "the refusal gave no reasons")
        request = self.request()
        self.assertEqual("review", request.step)
        self.assertEqual(["EPIC-001", "STORY-001"], request.work_items)
        self.assertEqual("drafted", request.step_outputs[-1].outcome)

        self.ok("backlog", "record", "REQUEST-001", "approve")
        self.assertEqual("done", self.request().step)
        self.assertEqual("The household cook.", self.request().questions[0].answer)
        story = self.item("stories", "STORY-001")
        self.assertEqual(("default", "captured", "EPIC-001"), (story.workflow, story.step, story.parent))
        self.assertIsNone(self.item("epics", "EPIC-001").step)
        self.assertEqual("", self.git("status", "--porcelain", cwd=self.product / "backlog"))


THREE_DRAFTS = """$DEV_TEAM backlog create epic "Meal planning" <<'ITEM'
overview: Plan a week of meals.
ITEM
$DEV_TEAM backlog create story "Plan a week" <<'ITEM'
parent: EPIC-001
overview: As a cook, I want to plan a week of meals.
ITEM
$DEV_TEAM backlog create story "Print the plan" <<'ITEM'
parent: EPIC-001
overview: As a cook, I want to print my plan.
ITEM
$DEV_TEAM backlog submit REQUEST-001 drafted <<'OUTPUT'
work_items: [EPIC-001, STORY-001, STORY-002]
OUTPUT
"""

REVISED_DRAFTS = """$DEV_TEAM backlog update STORY-001 <<'ITEM'
overview: As a cook, I want to plan a week of meals and print it.
ITEM
$DEV_TEAM backlog submit REQUEST-001 drafted <<'OUTPUT'
work_items: [EPIC-001, STORY-001]
dropped:
  - id: STORY-002
    reason: Printing is now part of planning a week.
OUTPUT
"""


class RevisingDrafts(Product):
    def test_a_revised_request_updates_one_draft_and_drops_another_which_the_customer_marks_wont_fix(self):
        self.script({"sh": THREE_DRAFTS}, {"sh": REVISED_DRAFTS})
        self.capture_and_analyse()
        self.ok("run", "--once")
        self.assertEqual("review", self.request().step)

        self.ok("backlog", "record", "REQUEST-001", "revise", stdin="feedback: Printing belongs with planning.\n")
        self.ok("run", "--once")
        request = self.request()
        self.assertEqual("review", request.step)
        self.assertEqual(["EPIC-001", "STORY-001"], request.work_items)
        self.assertEqual([("STORY-002", "Printing is now part of planning a week.")],
                         [(drop.id, drop.reason) for drop in request.dropped])
        self.assertIn("print", self.item("stories", "STORY-001").overview)

        self.ok("backlog", "record", "REQUEST-001", "approve")
        self.ok("backlog", "record", "STORY-002", "wontfix")
        dropped = self.item("stories", "STORY-002")
        self.assertEqual("wontfix", dropped.step)
        self.assertEqual([("captured", "wontfix", "wontfix")],
                         [(entry.step, entry.outcome, entry.to) for entry in dropped.step_outputs])
        self.assertNotEqual(0, self.dev_team("backlog", "record", "STORY-002", "analyse").returncode)

class AgentFailures(Product):
    def assertStillAtAnalysis(self, result):
        self.assertNotEqual(0, result.returncode)
        self.assertIn("REQUEST-001", result.stdout + result.stderr)
        request = self.request()
        self.assertEqual("analysis", request.step)
        self.assertEqual(["captured"], [entry.step for entry in request.step_outputs])

    def test_an_agent_that_exits_without_submitting_leaves_the_item_at_its_step(self):
        self.script({})
        self.capture_and_analyse()
        self.assertStillAtAnalysis(self.dev_team("run", "--once"))
        self.assertTrue((self.prompts / "01-claude.txt").exists(), "the engine did not run")

    def test_an_engine_exiting_with_an_error_leaves_the_item_at_its_step_despite_a_submission(self):
        self.script({"sh": QUESTIONS, "exit": 3})
        self.capture_and_analyse()
        self.assertStillAtAnalysis(self.dev_team("run", "--once"))
        self.assertTrue((self.prompts / "01-claude.txt").exists(), "the engine did not run")

    def test_a_missing_engine_command_is_reported_and_the_item_stays_at_its_step(self):
        (self.bin / "claude").unlink()
        self.script({"sh": QUESTIONS})
        self.capture_and_analyse()
        result = self.dev_team("run", "--once")
        self.assertStillAtAnalysis(result)
        self.assertIn("claude", result.stdout + result.stderr)
        self.assertFalse(self.prompts.exists(), "an engine ran")


class CustomerOutcomes(Product):
    def test_an_item_at_ready_can_be_marked_wont_fix(self):
        self.script({"sh": "$DEV_TEAM backlog submit STORY-001 analysed <<'OUTPUT'\n"
                           "acceptance_criteria: [A week of meals can be planned]\nOUTPUT\n"},
                    {"sh": "$DEV_TEAM backlog submit STORY-001 sound </dev/null"})
        self.ok("backlog", "create", "story", "Plan a week", stdin="overview: As a cook, I want to plan a week.\n")
        self.ok("backlog", "record", "STORY-001", "analyse")
        self.ok("run", "--once")
        self.assertEqual("ready", self.item("stories", "STORY-001").step)
        self.ok("backlog", "record", "STORY-001", "wontfix")
        self.assertEqual("wontfix", self.item("stories", "STORY-001").step)

    def test_invalid_output_is_refused_with_reasons_and_the_item_is_unchanged(self):
        self.ok("backlog", "create", "request", "Plan meals")
        path = self.product / "backlog" / "requests" / "REQUEST-001.yaml"
        before = path.read_bytes()
        for outcome, stdin in (("analyse", "feedback: Go\n"), ("finish", ""), ("analyse", "- a list\n")):
            with self.subTest(outcome=outcome, stdin=stdin):
                result = self.dev_team("backlog", "record", "REQUEST-001", outcome, stdin=stdin)
                self.assertNotEqual(0, result.returncode)
                self.assertTrue(result.stderr.strip(), "no reason given")
        self.assertEqual(before, path.read_bytes())

    def test_an_agent_step_is_not_recorded_as_the_customer(self):
        self.capture_and_analyse()
        result = self.dev_team("backlog", "record", "REQUEST-001", "questions", stdin="questions: []\n")
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("analysis", self.request().step)


class InvalidWorkflow(Product):
    def run_with_request_workflow(self, change):
        harness = self.base / "harness"
        for directory in ("devteam", "workflows", "prompts", "config", "roles", "standards"):
            shutil.copytree(ROOT / directory, harness / directory, ignore=shutil.ignore_patterns("__pycache__"))
        workflow = harness / "workflows" / "request.yaml"
        data = yaml.safe_load(workflow.read_text())
        change(data["steps"])
        workflow.write_text(yaml.safe_dump(data))
        self.script({"sh": QUESTIONS})
        result = self.dev_team("run", "--once", env={"PYTHONPATH": str(harness)})
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(self.prompts.exists(), "an engine ran")
        return result.stdout + result.stderr

    def test_an_invalid_workflow_is_reported_at_load_naming_the_step_and_problem(self):
        def lead_nowhere(steps):
            steps["analysis"]["outcomes"]["drafted"]["next"] = "reviewing"
        reported = self.run_with_request_workflow(lead_nowhere)
        for named in ("request", "analysis", "reviewing"):
            self.assertIn(named, reported)

    def test_a_customer_step_asking_for_an_input_the_tui_cannot_take_is_rejected_at_load(self):
        def ask_for_a_priority(steps):
            steps["review"]["output"]["properties"]["priority"] = {"type": "string"}
        reported = self.run_with_request_workflow(ask_for_a_priority)
        for named in ("request", "review", "priority"):
            self.assertIn(named, reported)


if __name__ == "__main__":
    unittest.main()
