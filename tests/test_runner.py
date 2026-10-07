import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from devteam import engines, git, tui, workflow
from devteam import runner as runners
from devteam.backlog import Repository
from devteam.config import Role
from devteam.runner import Runner, StepFailed, Waiting

WORKFLOW = {
    "initial": "captured",
    "steps": {
        "captured": {"owner": "human", "transitions": {"analyse": "analysis"}},
        "analysis": {"owner": "agent:analyst", "transitions": {"questions": "answering", "ready": "ready"}},
        "answering": {"owner": "human", "transitions": {"answered": "analysis"}},
        "ready": {"owner": "human", "transitions": {"play": "implement"}},
        "implement": {"owner": "agent:implementer", "transitions": {"implemented": "review"}},
        "review": {"owner": "agent:reviewer", "transitions": {"approve": "done", "revise": "implement"}},
        "done": {"owner": "human", "transitions": {}},
    },
}


def role(name, branch=False):
    return Role(name, "fake", f"{name}-model", 5, ["fake-cli", "{prompt}", "{model}", "{extra_dir}", "{permission}"],
                "write-mode", branch)


class FakeEngine:
    """Replies come from a per-item script; each entry is (exit code, reply) or a callable."""
    def __init__(self, script):
        self.script = {key: list(value) for key, value in script.items()}
        self.calls = []

    def __call__(self, role, prompt, cwd, extra_dir, log):
        item = next(key for key in self.script if f"/{key}.md" in prompt)
        self.calls.append((item, role, prompt, cwd, extra_dir))
        log.write_text("transcript")
        reply = self.script[item].pop(0)
        return reply(prompt) if callable(reply) else reply


class RunnerAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "product"
        workflows = Path(self.temp.name) / "workflows"
        workflows.mkdir()
        (workflows / "default.json").write_text(json.dumps(WORKFLOW))
        self.roles = {"analyst": role("analyst"), "implementer": role("implementer", True), "reviewer": role("reviewer", True)}
        self.repo = Repository(self.root, workflows, self.roles)
        self.epic = self.repo.create("epic", "Epic")
        self.story = self.repo.create("story", "First", "Body\n", parent=self.epic.id)
        self.other = self.repo.create("story", "Second", parent=self.epic.id)
        self.messages = []

    def runner(self, script, **options):
        self.engine = FakeEngine(script)
        return Runner(self.repo, self.roles, self.engine, self.messages.append, **options)

    def step(self, record):
        return self.repo.scan().valid[record.id].metadata["step"]

    def test_agent_step_invokes_configured_role_once_and_applies_transition(self):
        self.repo.transition(self.story.id, "analyse")
        runner = self.runner({"STORY-001": [(0, "Looks fine.\n\nTRANSITION: ready\n")]})
        runner.run(once=True)
        self.assertEqual("ready", self.step(self.story))
        [(item, used, prompt, cwd, extra_dir)] = self.engine.calls
        self.assertEqual(("analyst", "analyst-model"), (used.name, used.model))
        self.assertIn(str(self.story.path), prompt)
        self.assertIn("`questions` moves the item to `answering`", prompt)
        self.assertIn("`ready` moves the item to `ready`", prompt)
        self.assertEqual(self.root, extra_dir)
        self.assertEqual(1, len(list((self.root / "log" / "STORY-001").glob("analysis-*.log"))))
        self.assertIn("ready -> ready", self.messages[-1])

    def test_human_owned_and_terminal_steps_invoke_nothing(self):
        runner = self.runner({})
        self.assertEqual(0, runner.run_pass())
        self.assertEqual([], self.engine.calls)

    def test_failures_leave_the_step_and_are_not_retried(self):
        replies = {
            "nonzero exit": (3, "TRANSITION: ready"),
            "missing transition": (0, "All done."),
            "unknown transition": (0, "TRANSITION: play"),
            "transition not last": (0, "TRANSITION: ready\nand some more"),
            "empty": (0, ""),
        }
        self.repo.transition(self.story.id, "analyse")
        for name, reply in replies.items():
            with self.subTest(case=name):
                before = self.story.path.read_bytes()
                runner = self.runner({"STORY-001": [reply, (0, "TRANSITION: ready")]})
                runner.run(once=True)
                runner.run(once=True)
                self.assertEqual(1, len(self.engine.calls))
                self.assertEqual(before, self.story.path.read_bytes())
                self.assertIn("FAILED", self.messages[-1])
                self.assertIn(str(self.root / "log" / "STORY-001"), self.messages[-1])

    def test_agent_editing_front_matter_is_a_failure(self):
        self.repo.transition(self.story.id, "analyse")

        def tamper(prompt):
            self.story.path.write_text(self.story.path.read_text().replace("title: First", "title: Changed"))
            return 0, "TRANSITION: ready"
        self.runner({"STORY-001": [tamper]}).run(once=True)
        self.assertEqual("analysis", self.step(self.story))
        self.assertIn("front matter", self.messages[-1])

    def test_waiting_item_does_not_block_another(self):
        for record in (self.story, self.other):
            self.repo.transition(record.id, "analyse")
        self.runner({"STORY-001": [(0, "TRANSITION: questions")], "STORY-002": [(0, "TRANSITION: ready")]}).run(once=True)
        self.assertEqual("answering", self.step(self.story))
        self.assertEqual("ready", self.step(self.other))
        self.assertEqual(2, len(self.engine.calls))

    def test_questions_written_by_the_agent_survive_and_analysis_resumes(self):
        self.repo.transition(self.story.id, "analyse")

        def ask(prompt):
            with self.story.path.open("a") as fh:
                fh.write("\n## Questions\n\n1. Which users?\n")
            return 0, "I need an answer.\n**TRANSITION: questions**"
        runner = self.runner({"STORY-001": [ask, (0, "TRANSITION: ready")]})
        runner.run(once=True)
        self.assertEqual("answering", self.step(self.story))
        self.assertIn("## Questions\n\n1. Which users?", self.story.path.read_text())
        self.repo.transition(self.story.id, "answered")
        runner.run(once=True)
        self.assertEqual("ready", self.step(self.story))
        self.assertIn("1. Which users?", self.story.path.read_text())

    def test_run_limit_stops_an_agent_loop(self):
        self.roles = {name: role(name) for name in self.roles}
        self.repo.transition(self.story.id, "analyse")
        self.runner({"STORY-001": [(0, "TRANSITION: ready")]}).run(once=True)
        self.repo.transition(self.story.id, "play")
        loop = [(0, "TRANSITION: implemented"), (0, "TRANSITION: revise")] * 5
        self.runner({"STORY-001": loop}, max_runs=4).run(once=True)
        self.assertEqual(4, len(self.engine.calls))
        self.assertIn("already ran 4", self.messages[-1])

    def test_branch_role_outside_git_fails_without_invoking(self):
        self.repo.transition(self.story.id, "analyse")
        runner = self.runner({"STORY-001": [(0, "TRANSITION: ready")]})
        runner.run(once=True)
        self.repo.transition(self.story.id, "play")
        runner.run(once=True)
        self.assertEqual("implement", self.step(self.story))
        self.assertEqual(1, len(self.engine.calls))
        self.assertIn("git repository", self.messages[-1])


class HarnessSteps(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = Repository(self.root / "backlog")
        epic = self.repo.create("epic", "Delivery")
        self.story = self.repo.create("story", "Published item", parent=epic.id)
        self.other = self.repo.create("story", "Next item", parent=epic.id)
        self.engine = FakeEngine({})
        self.messages = []
        self.runner = Runner(self.repo, engine=self.engine, report=self.messages.append, max_runs=0)

    def at(self, step):
        # Place the fixture at the step under test without running the intervening agents.
        record = self.repo.scan().valid[self.story.id]
        record.path.write_text(record.path.read_text().replace(
            f"step: {record.metadata['step']}\n", f"step: {step}\n", 1))
        return self.repo.scan().valid[self.story.id]

    def test_registry_matches_the_validated_actions(self):
        self.assertEqual(workflow.HARNESS_ACTIONS, set(runners.HARNESS_ACTIONS))

    def test_harness_steps_run_without_engine_checkout_or_run_count(self):
        for action, target in (("merged", "done"), ("rejected", "implement")):
            with self.subTest(action=action):
                record = self.at(action)
                self.assertEqual([(record, self.repo.step(record))], self.runner.pending())
                self.assertEqual(1, self.runner.run_pass())
                self.assertEqual(target, self.repo.scan().valid[record.id].metadata["step"])
                self.assertIn(f"completed -> {target}", self.messages[-1])
                self.assertEqual([], self.engine.calls)
                self.assertEqual({}, self.runner.runs)
                self.assertEqual({}, self.runner.failed)

    def test_failure_waits_for_retry_or_restart(self):
        self.at("merged")
        calls = []

        def fail(runner, record):
            calls.append(record.id)
            raise StepFailed("cannot complete")

        with patch.dict(runners.HARNESS_ACTIONS, merged=fail):
            self.assertEqual(1, self.runner.run_pass())
            self.assertEqual("merged", self.repo.scan().valid[self.story.id].metadata["step"])
            self.assertIn("FAILED - cannot complete", self.messages[-1])
            self.assertEqual(0, self.runner.run_pass())
            self.assertEqual([self.story.id], calls)
            self.runner.retry(self.story.id)
            self.assertEqual(1, self.runner.run_pass())
            restarted = Runner(self.repo, engine=self.engine, report=self.messages.append)
            self.assertEqual(1, restarted.run_pass())
            self.assertEqual([self.story.id] * 3, calls)
        self.runner.retry(self.story.id)
        self.assertEqual(1, self.runner.run_pass())
        self.assertEqual("done", self.repo.scan().valid[self.story.id].metadata["step"])

    def test_pr_decision_holds_checkout_until_terminal(self):
        product = self.root / "product"
        product.mkdir()
        git.must(product, "init", "-q", "-b", "main")
        # A real, empty base commit in this temporary repository permits branch switching.
        git.must(product, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "init")
        self.runner.checkout = product
        self.runner.take_checkout(self.story)
        for step in ("pull-request", "rejected", "merged"):
            with self.subTest(step=step):
                self.at(step)
                with self.assertRaises(Waiting) as raised:
                    self.runner.take_checkout(self.other)
                self.assertIn(f"holds the checkout at step {step}", str(raised.exception))
        self.at("pull-request")
        row = next(row for row in tui.rows(self.repo) if row.key == self.story.id)
        self.assertTrue(row.needs_you)
        self.assertEqual("YOU", row.waiting_on)
        self.assertEqual([], self.runner.pending())
        self.at("done")
        self.assertEqual(f"devteam/{self.other.id}", self.runner.take_checkout(self.other))
        self.assertEqual(f"devteam/{self.other.id}", git.current_branch(product))


class EngineInvocation(unittest.TestCase):
    def test_brief_leads_the_prompt_when_the_engine_has_no_placeholder_for_it(self):
        without = Role("analyst", "x", "m", 5, ["cli", "{prompt}"], "w")
        with_flag = Role("analyst", "x", "m", 5, ["cli", "{prompt}", "--system", "{brief}"], "w")
        brief = without.brief()
        self.assertEqual(["cli", brief + "\n\ndo it"], engines.build_argv(without, "do it", Path("."), Path(".")))
        self.assertEqual(["cli", "do it", "--system", brief], engines.build_argv(with_flag, "do it", Path("."), Path(".")))

    def test_real_engine_wrapper_logs_and_returns_reply(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "run.log"
            echo = Role("analyst", "sh", "m1", 5, ["sh", "-c", "echo \"$0 {model} {permission}\"; echo oops >&2; exit 4",
                                                    "{prompt}"], "write-mode", False)
            code, reply = engines.run(echo, "hello", Path(directory), Path(directory), log)
            self.assertEqual((4, echo.brief() + "\n\nhello m1 write-mode\n"), (code, reply))
            self.assertIn("oops", log.read_text())
            missing = Role("analyst", "none", "m1", 5, ["definitely-not-a-command-xyz"], "w", False)
            self.assertEqual((127, ""), engines.run(missing, "p", Path(directory), Path(directory), log))


if __name__ == "__main__":
    unittest.main()
