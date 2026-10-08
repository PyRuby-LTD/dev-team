import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from devteam import check, git, questions, tui
from devteam.backlog import Repository
from devteam.cli import main
from devteam.config import Role
from devteam.runner import Runner

WORKFLOW = {
    "initial": "implement",
    "steps": {
        "implement": {"owner": "agent:implementer", "transitions": {"implemented": "test"}},
        "test": {"owner": "agent:tester", "transitions": {"written": "verify", "defect": "implement"}},
        "verify": {"owner": "check", "transitions": {"passed": "review", "failed": "test"}},
        "review": {"owner": "human", "transitions": {}},
    },
}
IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
SCRIPT = 'echo "ran ${1:-everything}"; test "$1" != TEST=bad'


class ProjectCheck(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.config = check.Check(["sh", "-c", SCRIPT, "check"], "TEST={name}", 5)

    def test_whole_check_and_single_test_use_the_configured_command(self):
        log = self.directory / "logs" / "run.log"
        self.assertEqual((0, "ran everything\n"), check.run(self.directory, config=self.config, log=log))
        self.assertIn("# exit 0", log.read_text())
        self.assertEqual((0, "ran TEST=one.test\n"), check.run(self.directory, "one.test", config=self.config))
        self.assertEqual((1, "ran TEST=bad\n"), check.run(self.directory, "bad", config=self.config))

    def test_timeout_and_missing_command_are_failures(self):
        slow = check.Check(["sh", "-c", "echo started; sleep 5"], "{name}", 1)
        code, output = check.run(self.directory, config=slow)
        self.assertEqual(124, code)
        self.assertIn("started", output)
        self.assertIn("timed out after 1 seconds", output)
        self.assertEqual(127, check.run(self.directory, config=check.Check(["no-such-command-xyz"], "{name}", 1))[0])

    def test_launch_outcomes_are_distinct_from_real_exit_codes(self):
        for code in (124, 127):
            with self.subTest(code=code):
                result = check.run(self.directory, config=check.Check(["sh", "-c", f"exit {code}"], "{name}", 5))
                self.assertEqual(code, result[0])
                self.assertEqual("finished", result.status)
        missing = check.run(self.directory, config=check.Check(["no-such-command-xyz"], "{name}", 1))
        self.assertEqual("could not be started", missing.status)
        slow = check.run(self.directory, config=check.Check(["sh", "-c", "sleep 2"], "{name}", 0.01))
        self.assertEqual("timed out", slow.status)

    def test_configured_check_is_the_makefile_target(self):
        config = check.load()
        self.assertEqual((["make", "regression"], "TEST=x"), (config.command, config.one.format(name="x")))
        makefile = (Path(__file__).resolve().parents[1] / "Makefile").read_text()
        self.assertIn("regression:", makefile)
        self.assertIn("$(TEST)", makefile)

    def test_long_output_is_cut_to_its_end(self):
        output = "\n".join(f"line {n}" for n in range(200)) + "\n"
        text = check.tail(output, 10)
        self.assertTrue(text.startswith("... 190 earlier lines omitted ..."))
        self.assertTrue(text.endswith("line 199"))
        self.assertIn("FAILED (exit 2)", check.summary(2, output, "the project check"))
        self.assertTrue(check.summary(0, "ok\n", "the project check").startswith("Passed"))

    def test_cli_prints_a_short_result_and_exits_with_the_check_code(self):
        calls = []

        def fake(directory, name=None, log=None, config=None):
            calls.append((directory, name))
            return (0, "fine\n") if name != "bad" else (3, "boom\n")
        with patch("devteam.check.run", fake):
            for name, code in ((None, 0), ("bad", 3)):
                with contextlib.redirect_stdout(io.StringIO()) as output, self.assertRaises(SystemExit) as exit:
                    main(["--product", self.temp.name, "check"] + ([name] if name else []))
                self.assertEqual(code, exit.exception.code)
                self.assertIn("check passed" if code == 0 else "check FAILED (exit 3)", output.getvalue())
        self.assertEqual([(self.directory.resolve(), None), (self.directory.resolve(), "bad")], calls)


class Sections(unittest.TestCase):
    def test_section_is_added_then_replaced_in_place(self):
        first = questions.replace_section("Intro.\n", "Test run", "Passed")
        self.assertEqual("Intro.\n\n## Test run\n\nPassed\n", first)
        second = questions.replace_section(first + "\n## Review\n\nFine.\n", "Test run", "FAILED\nmore")
        self.assertEqual("Intro.\n\n## Test run\n\nFAILED\nmore\n\n## Review\n\nFine.\n", second)


class VerifyStep(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patcher = patch.dict(os.environ, IDENTITY)
        patcher.start()
        self.addCleanup(patcher.stop)
        base = Path(self.temp.name).resolve()
        self.product = base / "product"
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.product)], check=True)
        (self.product / "app.txt").write_text("v1\n")
        git.commit_all(self.product, "init")
        workflows = base / "workflows"
        workflows.mkdir()
        (workflows / "default.json").write_text(json.dumps(WORKFLOW))
        self.roles = {name: Role(name, "fake", "m", 5, ["fake"], "w", True) for name in ("implementer", "tester")}
        self.repo = Repository(git.ensure_backlog(self.product), workflows, self.roles)
        self.epic = self.repo.create("epic", "Epic")
        self.story = self.repo.create("story", "Story", "Body.\n", parent=self.epic.id)
        self.results = []
        self.checked = []
        self.replies = {"implementer": "implemented", "tester": "written"}
        self.messages = []
        self.runner = Runner(self.repo, self.roles, self.engine, self.messages.append, checkout=self.product,
                             check=self.check)

    def engine(self, role, prompt, cwd, extra_dir, log):
        log.write_text("transcript")
        (cwd / f"{role.name}.txt").write_text(f"{len(self.checked)}\n")
        return 0, f"TRANSITION: {self.replies[role.name]}"

    def check(self, directory, name=None, log=None, config=None):
        self.checked.append((directory, name, git.current_branch(directory), git.clean(directory)))
        log.write_text("full output")
        return self.results.pop(0)

    def current(self):
        return self.repo.scan().valid[self.story.id]

    def test_harness_runs_the_whole_check_on_the_item_branch_and_passes_to_review(self):
        self.results = [(0, "all good\n")]
        self.runner.run(once=True)
        self.assertEqual([(self.product, None, "devteam/STORY-001", True)], self.checked)
        self.assertEqual("review", self.current().metadata["step"])
        body = self.current().body
        self.assertIn("## Test run\n\nRun by the harness", body)
        self.assertIn("passed (exit 0)", body)
        self.assertNotIn("all good", body)
        self.assertNotIn("```", body)
        self.assertIn("duration", body)
        self.assertIn("STORY-001 verify (check): passed -> review", self.messages)

    def test_failure_returns_to_the_tester_and_the_result_is_replaced_next_time(self):
        self.results = [(2, "boom\n"), (0, "fixed\n")]
        self.runner.run(once=True)
        self.assertEqual("review", self.current().metadata["step"])
        self.assertEqual(2, len(self.checked))
        body = self.current().body
        self.assertEqual(1, body.count("## Test run"))
        self.assertNotIn("boom", body)
        self.assertIn("STORY-001 verify (check): failed -> test", self.messages)
        history = git.must(self.repo.root, "log", "--format=%s").splitlines()
        self.assertIn("STORY-001: failed -> test", history)

    def test_verdict_is_opaque_and_launch_errors_have_no_exit_code(self):
        self.repo.transition(self.story.id, "implemented")
        self.repo.transition(self.story.id, "written")
        step = self.repo.step(self.current())
        cases = [
            (check.Result(0, "FAILED Traceback"), "passed (exit 0)", "passed"),
            (check.Result(124, "OK"), "failed (exit 124)", "failed"),
            (check.Result(127, "OK"), "failed (exit 127)", "failed"),
            (check.Result(124, "secret", "timed out"), "timed out", "failed"),
            (check.Result(127, "secret", "could not be started"), "could not be started", "failed"),
        ]
        log = self.repo.root / "log" / self.story.id / "verify-unit.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        for outcome, expected, transition in cases:
            with self.subTest(expected=expected):
                self.results = [outcome]
                # Test the record writer on the branch without running the later agent loop.
                if self.current().metadata["step"] != "verify":
                    self.repo.transition(self.story.id, "written")
                with patch("devteam.config.ROOT", Path("/home/fixture/harness")), \
                        patch("sys.executable", "/home/fixture/python/bin/python"), \
                        patch("sys.prefix", "/home/fixture/python"):
                    name, updated = self.runner.verify(self.current(), step, log)
                body = updated.body
                self.assertEqual(transition, name)
                self.assertIn(expected, body)
                self.assertNotIn(outcome[1], body)
                self.assertNotIn(str(self.product), body)
                self.assertNotIn(str(log), body)
                self.assertNotIn("/home/fixture", body)
                if outcome.status != "finished":
                    self.assertNotIn("exit", body)
                # The successful case ends at the human review step; return to verify.
                if name == "passed":
                    text = self.story.path.read_text().replace("step: review", "step: verify")
                    self.story.path.write_text(text)

    def test_check_steps_count_towards_the_run_limit(self):
        self.results = [(1, "no\n")] * 10
        self.runner.max_runs = 5
        self.runner.run(once=True)
        self.assertIn("already ran 5 steps", self.messages[-1])
        self.assertLessEqual(len(self.checked), 2)

    def test_terminal_ui_shows_the_step_as_waiting_on_checks_not_on_you(self):
        self.repo.transition(self.story.id, "implemented")
        self.repo.transition(self.story.id, "written")
        row = next(row for row in tui.rows(self.repo, self.runner) if row.key == self.story.id)
        self.assertEqual(("verify", "checks", False), (row.step, row.waiting_on, row.needs_you))
        self.assertEqual([record.id for record, step in self.runner.pending()], [self.story.id])


if __name__ == "__main__":
    unittest.main()
