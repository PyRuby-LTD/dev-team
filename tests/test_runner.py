import json
from pathlib import Path
import tempfile
import unittest

from devteam import engines
from devteam.backlog import Repository
from devteam.config import Role
from devteam.runner import Runner

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


class EngineInvocation(unittest.TestCase):
    def test_real_engine_wrapper_logs_and_returns_reply(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "run.log"
            echo = Role("analyst", "sh", "m1", 5, ["sh", "-c", "echo \"$0 {model} {permission}\"; echo oops >&2; exit 4",
                                                    "{prompt}"], "write-mode", False)
            code, reply = engines.run(echo, "hello", Path(directory), Path(directory), log)
            self.assertEqual((4, "hello m1 write-mode\n"), (code, reply))
            self.assertIn("oops", log.read_text())
            missing = Role("analyst", "none", "m1", 5, ["definitely-not-a-command-xyz"], "w", False)
            self.assertEqual((127, ""), engines.run(missing, "p", Path(directory), Path(directory), log))


if __name__ == "__main__":
    unittest.main()
