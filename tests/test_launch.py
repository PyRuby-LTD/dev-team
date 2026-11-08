"""Launching dev-team: setup is a prerequisite, and the harness, run as its command, brings its own workflows.

The tests that need a process of their own run the dev-team command with stub engines on the PATH following a plan of
shell turns: launching a copied harness from outside it, workflows reported invalid at load, and one journey through
the command line and a real engine invocation.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml


from tests.journey import GIT, ROOT, Product
from tests.test_request_journey import QUESTIONS

SCRIPTED = ROOT / "tests" / "stubs" / "scripted"
DEV_TEAM = f"{sys.executable} -P -m devteam"
TOOLS = ("git", "sh", "env", "python3")

SHELL_QUESTIONS = """$DEV_TEAM backlog submit REQUEST-001 questions <<'OUTPUT'
questions:
  - question: Who plans the meals?
OUTPUT
"""

SHELL_DRAFTS = """$DEV_TEAM backlog create epic "Meal planning" <<'ITEM'
overview: Plan a week of meals.
ITEM
$DEV_TEAM backlog submit REQUEST-001 drafted <<'OUTPUT'
work_items: [EPIC-001]
OUTPUT
"""


class Installed(unittest.TestCase):
    """A product driven through the dev-team command, as the launcher alias runs it."""

    def setUp(self):
        self.base = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.product = self.base / "product"
        self.product.mkdir()
        environment = {**os.environ, **GIT}
        for args in (("init", "-q", "-b", "main"), ("commit", "-q", "--allow-empty", "-m", "Start"),
                     ("remote", "add", "origin", "git@github.com:o/meals.git")):
            subprocess.run(["git", *args], cwd=self.product, env=environment, check=True)
        (self.product / "Makefile").write_text("regression:\n\ttrue\n")
        subprocess.run(["git", "add", "-A"], cwd=self.product, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "Add a regression target"], cwd=self.product, env=environment,
                       check=True)
        self.prompts = self.base / "prompts"
        self.plan = self.base / "plan.json"
        self.bin = self.base / "bin"
        self.bin.mkdir()
        for tool in TOOLS:
            (self.bin / tool).symlink_to(shutil.which(tool))
        for name in ("claude", "codex"):
            shutil.copy(SCRIPTED, self.bin / name)
            (self.bin / name).chmod(0o755)
        self.ok("init")

    def dev_team(self, *args, stdin="", env=None):
        environment = {**os.environ, **GIT, "PATH": str(self.bin), "DEV_TEAM": DEV_TEAM,
                       "STUB_PLAN": str(self.plan), "STUB_PROMPTS": str(self.prompts), **(env or {})}
        return subprocess.run([*DEV_TEAM.split(), *args], cwd=self.product, env=environment, input=stdin,
                              capture_output=True, text=True, timeout=120)

    def ok(self, *args, stdin="", env=None):
        result = self.dev_team(*args, stdin=stdin, env=env)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        return result

    def script(self, *shells):
        self.plan.write_text(json.dumps([{"sh": shell} for shell in shells]))

    def request(self):
        return yaml.safe_load((self.product / "backlog" / "requests" / "REQUEST-001.yaml").read_text())

    def copied_harness(self):
        harness = self.base / "harness"
        for directory in ("devteam", "workflows", "prompts", "config", "roles", "standards"):
            shutil.copytree(ROOT / directory, harness / directory, ignore=shutil.ignore_patterns("__pycache__"))
        return harness


class CommandLine(Installed):
    def test_a_request_is_captured_analysed_by_an_engine_answered_and_drafted_through_the_command(self):
        self.script(SHELL_QUESTIONS, SHELL_DRAFTS)
        self.ok("backlog", "create", "request", "Plan meals", stdin="overview: Plan meals.\n")
        self.ok("backlog", "record", "REQUEST-001", "analyse")
        self.ok("run", "--once")
        self.assertEqual("answering", self.request()["step"])
        self.ok("backlog", "record", "REQUEST-001", "answered",
                stdin="questions:\n  - question: Who plans the meals?\n    answer: The household cook.\n")
        self.ok("run", "--once")
        self.ok("backlog", "record", "REQUEST-001", "approve")
        self.assertEqual(("done", ["EPIC-001"]), (self.request()["step"], self.request()["work_items"]))
        self.assertTrue(self.ok("prompt", "analysis", "--item", "REQUEST-001").stdout.strip())

    def test_a_refusal_exits_nonzero_with_its_reason(self):
        self.ok("backlog", "create", "request", "Plan meals")
        result = self.dev_team("backlog", "record", "REQUEST-001", "finish")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("finish", result.stderr)

    def test_a_failed_step_exits_nonzero_naming_the_item(self):
        self.script("true")
        self.ok("backlog", "create", "request", "Plan meals")
        self.ok("backlog", "record", "REQUEST-001", "analyse")
        result = self.dev_team("run", "--once")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("REQUEST-001", result.stdout + result.stderr)


class ProductOutsideTheHarness(Installed):
    def test_work_items_land_in_the_products_backlog_while_the_harness_brings_its_own_workflows(self):
        harness = self.copied_harness()
        for directory in ("workflows", "config"):
            (self.product / directory).mkdir()
        (self.product / "workflows" / "request.yaml").write_text("not: [a workflow\n")
        (self.product / "config" / "roles.toml").write_text("not toml\n")
        self.script(SHELL_QUESTIONS)
        environment = {"PYTHONPATH": str(harness)}

        self.ok("backlog", "create", "request", "Plan meals", stdin="overview: Plan meals.\n", env=environment)
        self.ok("backlog", "record", "REQUEST-001", "analyse", env=environment)
        self.ok("run", "--once", env=environment)

        self.assertEqual("answering", self.request()["step"])
        self.assertFalse((harness / "backlog").exists(), "the harness kept a backlog of its own")
        self.assertEqual([], list(harness.rglob("REQUEST-001*")))


class InvalidWorkflow(Installed):
    def run_with_request_workflow(self, change):
        harness = self.copied_harness()
        workflow = harness / "workflows" / "request.yaml"
        data = yaml.safe_load(workflow.read_text())
        change(data["steps"])
        workflow.write_text(yaml.safe_dump(data))
        self.script(SHELL_QUESTIONS)
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


class UnsetProduct(Product):
    def set_up_product(self):
        pass

    def commit_makefile(self, text):
        (self.product / "Makefile").write_text(text)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "Add a Makefile")

    def assertLaunchRefused(self):
        self.script(QUESTIONS)
        for launch in (self.team.run, self.team.harness):
            with self.subTest(launch=launch.__name__):
                self.assertTrue(self.refused(launch).strip(), "nothing reported")
        self.assertEqual([], self.agent.agents, "an engine ran")

    def test_a_product_without_a_backlog_branch_is_refused_and_launch_does_not_create_one(self):
        self.commit_makefile("regression:\n\ttrue\n")
        self.assertLaunchRefused()
        self.assertFalse(self.git("branch", "--list", "devteam-backlog").strip(), "launch set up the backlog")

    def test_a_product_without_a_regression_target_is_refused(self):
        self.commit_makefile("build:\n\ttrue\n")
        self.team.init()
        self.assertLaunchRefused()


class InitialisingAnEmptyRepository(Product):
    def set_up_product(self):
        self.empty = self.base / "empty"
        self.remote = self.base / "remote.git"
        self.git("init", "-q", "-b", "main", str(self.empty))
        self.git("init", "-q", "--bare", str(self.remote))
        self.git("remote", "add", "origin", "git@github.com:o/empty.git", cwd=self.empty)
        self.git("config", f"url.{self.remote}.insteadOf", "git@github.com:o/empty.git", cwd=self.empty)

    def state(self):
        return (self.git("for-each-ref", cwd=self.empty), self.git("for-each-ref", cwd=self.remote),
                self.git("status", "--porcelain", cwd=self.empty), (self.empty / "Makefile").read_text())

    def test_init_sets_up_an_empty_repository_and_a_second_run_changes_nothing(self):
        self.script(QUESTIONS)
        team = self.dev_team(self.empty)
        team.init()
        self.assertEqual({}, team.run(once=True))
        self.assertIn("refs/heads/devteam-backlog", self.git("for-each-ref", cwd=self.empty))
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.empty),
                         self.git("rev-parse", "refs/heads/main", cwd=self.remote))

        before = self.state()
        team.init()
        self.assertEqual(before, self.state())


if __name__ == "__main__":
    unittest.main()
