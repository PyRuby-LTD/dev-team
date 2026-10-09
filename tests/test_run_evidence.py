"""STORY-014: run evidence stays out of the committed record, and machine paths never reach git.

The harness is started as a process through its command line. The engines (claude, codex) and the
project's check (make) are stand-in executables on PATH; gh is the offline stub used elsewhere.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

from textual.widgets import TextArea, Tree

from devteam import check as checks
from devteam import git as repo_git
from devteam import tui
from devteam.backlog import Repository
from devteam.config import Role
from devteam.evidence import PathGuard
from devteam.runner import Runner

ROOT = Path(__file__).resolve().parents[1]
STUBS = ROOT / "tests" / "stubs"
FIXTURES = ROOT / "tests" / "fixtures" / "gh"
IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
ISOLATED_GIT = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
TO_VERIFY = ("analyse", "analysed", "sound", "play", "implemented", "written")
TO_ACCEPT = TO_VERIFY + ("passed", "approve")
TO_PULL_REQUEST = TO_ACCEPT + ("pr", "published")
# Built at run time so that this file does not hold a home-style path itself.
NAME = "fixture" + "person"
HOME = "/home/" + NAME
STAMP = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC")

MAKE = """#!/bin/sh
echo "$@" > "$STUB_MAKE_ARGS"
printf '%s\\n' "$CHECK_OUTPUT"
exit "${CHECK_EXIT:-0}"
"""


def section(text, name):
    found = re.search(rf"^## {name}\n(.*?)(?=^## |\Z)", text, re.DOTALL | re.MULTILINE)
    return found.group(1) if found else None


def flat(text):
    return " ".join(text.split())


class Product(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.remote = self.base / "remote.git"
        self.product = self.base / "product"
        self.bin = self.base / "bin"
        self.prompts = self.base / "prompts"
        self.plan_file = self.base / "plan.json"
        self.make_args = self.base / "make-args"
        self.bin.mkdir()
        for engine in ("claude", "codex"):
            shutil.copy(STUBS / "scripted", self.bin / engine)
        shutil.copy(STUBS / "gh", self.bin / "gh")
        (self.bin / "make").write_text(MAKE)
        for tool in self.bin.iterdir():
            tool.chmod(0o755)
        self.git(self.base, "init", "-q", "--bare", "-b", "main", str(self.remote))
        self.git(self.base, "clone", "-q", str(self.remote), str(self.product))
        (self.product / "app.txt").write_text("v1\n")
        self.git(self.product, "add", "-A")
        self.git(self.product, "commit", "-q", "-m", "initial")
        self.git(self.product, "push", "-q", "origin", "main")
        self.backlog = self.product / "backlog"
        self.item = self.backlog / "stories" / "STORY-001.md"
        self.plan()
        self.devteam("backlog", "capture", "epic", "Epic", "--id", "EPIC-001")
        self.devteam("backlog", "capture", "story", "Story", "--id", "STORY-001", "--parent", "EPIC-001")

    def git(self, directory, *args):
        return subprocess.run(["git", *args], cwd=directory, env={**os.environ, **IDENTITY, **ISOLATED_GIT},
                              capture_output=True, text=True, check=True).stdout

    def plan(self, *entries):
        self.plan_file.write_text(json.dumps(list(entries)))

    def environment(self, path=None, **extra):
        env = {**os.environ, **IDENTITY, **ISOLATED_GIT,
               "PATH": path or f"{self.bin}{os.pathsep}{os.environ['PATH']}",
               "STUB_PLAN": str(self.plan_file), "STUB_PROMPTS": str(self.prompts),
               "STUB_MAKE_ARGS": str(self.make_args), "BACKLOG": str(self.backlog),
               "GH_STUB_ARGV": str(self.base / "gh-argv"), "GH_STUB_FIXTURES": str(FIXTURES),
               "ROOT": str(ROOT), "DEVTEAM": f"{sys.executable} -m devteam --product {self.product}"}
        env.update(extra)
        return env

    def devteam(self, *args, path=None, ok=True, **extra):
        result = subprocess.run([sys.executable, "-m", "devteam", "--product", str(self.product), *args],
                                cwd=ROOT, env=self.environment(path, **extra), capture_output=True, text=True,
                                timeout=120)
        if ok:
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        return result

    def move(self, *transitions):
        for transition in transitions:
            self.devteam("backlog", "move", "STORY-001", transition)

    def run_once(self, **extra):
        result = self.devteam("run", "--once", **extra)
        return result.stdout + result.stderr

    def text(self, path=None):
        return (path or self.item).read_text()

    def body(self, path=None):
        return self.text(path).split("\n---\n", 1)[1]

    def step(self):
        return re.search(r"^step: (.*)$", self.text(), re.MULTILINE).group(1)

    def subjects(self):
        return self.git(self.backlog, "log", "--format=%s").splitlines()

    def history(self):
        return self.git(self.backlog, "log", "-p", "--format=%H %s")

    def logs(self, item="STORY-001", pattern="verify-*.log"):
        return sorted((self.backlog / "log" / item).glob(pattern))

    def saved(self, item="STORY-001"):
        return self.logs(item, "unmasked-*.md")

    def prompt(self, number):
        return flat(next(self.prompts.glob(f"{number:02d}-*.txt")).read_text())

    def assert_never_committed(self, *values):
        history = self.history()
        for value in values or (NAME,):
            self.assertNotIn(value, history)

    def assert_no_machine_path(self, text):
        for path in (str(self.product), str(ROOT), sys.executable, sys.prefix, "/home/", "/tmp/"):
            self.assertNotIn(path, text)


class TestRunRecord(Product):
    """The harness's own check of the item's branch records an outcome and nothing else."""

    def setUp(self):
        super().setUp()
        self.move(*TO_VERIFY)

    def verify(self, code, output, **extra):
        return self.run_once(CHECK_EXIT=str(code), CHECK_OUTPUT=output, **extra)

    def record(self):
        return section(self.body(), "Test run")

    def test_passing_check_is_recorded_as_an_outcome_with_the_output_in_the_log(self):
        self.verify(0, f"MARKER-PASS ran in {self.product}\nsecond line")
        record = self.record()
        self.assertIn("passed", record)
        self.assertIn("exit 0", record)
        self.assertRegex(record, STAMP)
        self.assertRegex(record, r"\d+(\.\d+)? seconds")
        self.assertNotIn("MARKER-PASS", record)
        self.assertNotIn("```", record)
        self.assert_no_machine_path(record)
        [log] = self.logs()
        self.assertIn("MARKER-PASS", log.read_text())
        self.assertIn("STORY-001: passed -> review", self.subjects())
        self.assertNotIn("MARKER-PASS", self.history())

    def test_failing_check_is_recorded_as_failed_with_its_exit_code_and_no_output_or_log_path(self):
        self.verify(3, f"MARKER-FAIL in {self.product}/tests/x.py")
        record = self.record()
        self.assertIn("failed", record)
        self.assertIn("exit 3", record)
        self.assertNotIn("MARKER-FAIL", self.text())
        self.assertNotIn("verify-", self.text())
        [log] = self.logs()
        self.assertIn("MARKER-FAIL", log.read_text())
        self.assertNotIn(str(log), self.text())
        self.assertIn("STORY-001: failed -> test", self.subjects())
        self.assertNotIn("MARKER-FAIL", self.history())
        self.assertNotIn("verify-", self.history())

    def test_a_check_that_really_exits_124_or_127_is_a_failure_with_that_exit_code(self):
        for code in (124, 127):
            with self.subTest(code=code):
                self.verify(code, "real exit")
                record = self.record()
                self.assertIn(f"failed (exit {code})", record)
                self.assertNotIn("timed out", record)
                self.assertNotIn("could not be started", record)
                self.assertEqual("test", self.step())
                self.move("written")

    def test_failure_words_in_the_output_of_a_passing_check_do_not_change_the_verdict(self):
        self.verify(0, "Traceback (most recent call last):\nFAILED (errors=1)\nFAILED")
        self.assertIn("passed (exit 0)", self.record())
        self.assertIn("STORY-001: passed -> review", self.subjects())

    def test_ok_in_the_output_of_a_failing_check_does_not_change_the_verdict(self):
        self.verify(1, "Ran 3 tests\n\nOK\n")
        self.assertIn("failed (exit 1)", self.record())
        self.assertIn("STORY-001: failed -> test", self.subjects())

    def test_a_check_that_cannot_be_started_is_recorded_without_an_exit_code(self):
        path = self.base / "no-make"
        path.mkdir()
        for tool in ("git", "sh"):
            (path / tool).symlink_to(shutil.which(tool))
        self.verify(0, "", path=str(path))
        record = self.record()
        self.assertIn("could not be started", record)
        self.assertNotIn("exit", record)
        self.assertNotIn("passed", record)
        self.assertIn("STORY-001: failed -> test", self.subjects())
        [log] = self.logs()
        self.assertIn("could not start make", log.read_text())

    def test_a_check_that_times_out_is_recorded_without_an_exit_code(self):
        slow = checks.Check(["sh", "-c", "echo started; sleep 10"], "{name}", 0.5)
        repository = Repository(self.backlog, guard=PathGuard(self.product))
        roles = {name: Role(name, "fake", "m", 5, ["fake"], "w") for name in ("tester", "reviewer")}
        runner = Runner(repository, roles, lambda *args, **kwargs: (97, ""), lambda message: None,
                        checkout=self.product, check=lambda directory, log=None: checks.run(directory, log=log, config=slow))
        runner.run(once=True)
        record = section(self.body(), "Test run")
        self.assertIn("timed out", record)
        self.assertNotIn("exit", record)
        self.assertNotIn("124", record)
        [log] = self.logs()
        self.assertIn("timed out after", log.read_text())
        self.assertIn("STORY-001: failed -> test", self.subjects())

    def test_the_tester_after_a_failure_is_pointed_at_the_log_that_failed(self):
        self.verify(2, "boom")
        [log] = self.logs()
        prompt = self.prompt(1)
        self.assertIn(str(log), prompt)
        self.assertIn("relative path of the failing run", prompt)
        self.assertIn("what it expected", prompt)


class TestCheckCommand(Product):
    def test_check_prints_the_log_path_relative_to_the_checkout_and_writes_it_there(self):
        result = self.devteam("check", ok=False, CHECK_OUTPUT="MARKER-CHECK", CHECK_EXIT="0")
        self.assertEqual(0, result.returncode)
        printed = re.search(r"full output: (backlog/log/check/\S+\.log)$", result.stdout.strip())
        self.assertIsNotNone(printed, result.stdout)
        self.assertIn("MARKER-CHECK", (self.product / printed.group(1)).read_text())
        self.assertNotIn(str(self.product), result.stdout)
        self.assertEqual("regression", self.make_args.read_text().strip())

    def test_check_of_one_test_passes_its_name_on_and_keeps_the_exit_code(self):
        result = self.devteam("check", "one.test", ok=False, CHECK_EXIT="3", CHECK_OUTPUT="no")
        self.assertEqual(3, result.returncode)
        self.assertIn("check FAILED (exit 3); full output: backlog/log/check/", result.stdout)
        self.assertEqual("regression TEST=one.test", self.make_args.read_text().strip())
        self.assertNotIn(str(self.product), result.stdout)


class TestStoryFromStartToPublication(Product):
    def run_story(self):
        self.move("analyse")
        self.plan({"reply": "analysed"}, {"reply": "sound"},
                  {"reply": "implemented", "sh": "echo change > feature.txt"}, {"reply": "written"},
                  {"reply": "approve"}, {"reply": "published"})
        output = self.run_once()
        self.assertEqual("ready", self.step(), output)
        self.move("play")
        output += self.run_once()
        self.assertEqual("accept", self.step(), output)
        self.move("pr")
        return output + self.run_once()

    def test_every_agent_prompt_carries_the_evidence_rules_and_the_workflow_check_log(self):
        self.run_story()
        self.assertEqual("pull-request", self.step())
        evidence = str(self.backlog / "log" / "STORY-001")
        names = [next(self.prompts.glob(f"{n:02d}-*.txt")).name for n in range(1, 7)]
        self.assertEqual(["claude", "claude", "codex", "claude", "claude", "claude"],
                         [name.split("-")[1].removesuffix(".txt") for name in names])
        for number in range(1, 7):
            with self.subTest(prompt=number):
                prompt = self.prompt(number)
                self.assertIn(evidence, prompt)
                self.assertIn("cite the path the command prints", prompt)
                self.assertIn("Do not copy that output", prompt)
                self.assertIn("without pasting output", prompt)
                self.assertIn("relative to the repository", prompt)
                self.assertIn("`dev-team`", prompt)
                self.assertNotIn("{{", prompt)
                self.assertNotIn("actual output", prompt)
                self.assertNotIn("under `## Test run`", prompt)
        [log] = self.logs()
        self.assertIn("No workflow check has run yet.", self.prompt(3))
        self.assertIn("No workflow check has run yet.", self.prompt(4))
        self.assertIn(str(log), self.prompt(5))
        self.assertNotIn("No workflow check has run yet.", self.prompt(5))
        self.assertIn("Do not put absolute paths, home directories or command output in the pull request body",
                      self.prompt(6))

    def test_no_prompt_or_brief_tells_an_agent_to_read_or_paste_test_output_in_the_item(self):
        for path in [*(ROOT / "prompts").rglob("*.md"), *(ROOT / "roles").glob("*.md")]:
            with self.subTest(path=path.name):
                text = flat(path.read_text())
                self.assertNotIn("actual output", text)
                self.assertNotIn("only test output you should trust", text)
                self.assertNotRegex(text, r"(?i)(read|see|under) (a failure )?in `## Test run`")

    def test_the_record_copied_for_publication_matches_the_item_and_no_log_is_tracked_in_the_product(self):
        self.run_story()
        copy = self.git(self.product, "show", "devteam/STORY-001:docs/work-items/STORY-001.md")
        self.assertIn("passed (exit 0)", section(copy, "Test run"))
        self.assert_no_machine_path(copy)
        branches = self.git(self.product, "for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes").split()
        self.assertIn("refs/heads/devteam/STORY-001", branches)
        for branch in branches:
            with self.subTest(branch=branch):
                files = self.git(self.product, "ls-tree", "-r", "--name-only", branch).splitlines()
                self.assertEqual([], [name for name in files if "log/" in name or name.startswith("backlog/")])
        backlog_files = self.git(self.backlog, "ls-tree", "-r", "--name-only", "devteam-backlog").splitlines()
        self.assertEqual([], [name for name in backlog_files if name.startswith("log/")])


class TestPublicationCopy(Product):
    def test_a_body_that_trips_nothing_is_copied_unchanged(self):
        self.move(*TO_ACCEPT)
        self.move("pr")
        self.plan({"reply": "published"})
        self.run_once()
        copy = self.git(self.product, "show", "devteam/STORY-001:docs/work-items/STORY-001.md")
        self.assertEqual(self.git(self.backlog, "show", "HEAD~1:stories/STORY-001.md").split("\n---\n", 1)[1],
                         copy.split("\n---\n", 1)[1])

    def test_a_tripping_body_is_masked_in_the_copy_and_the_step_carries_on(self):
        self.move(*TO_ACCEPT)
        self.move("pr")
        with self.item.open("a") as fh:
            fh.write(f"\nOutput kept in `{HOME}/out/log.txt` and {self.product}/src/app.py.\n")
        number = len(self.item.read_text().splitlines())
        self.plan({"reply": "published"})
        output = self.run_once()
        copy = self.git(self.product, "show", "devteam/STORY-001:docs/work-items/STORY-001.md")
        self.assertIn("Output kept in `<path>` and src/app.py.", copy)
        self.assertNotIn(NAME, copy)
        self.assertNotIn(str(self.product), copy)
        self.assertIn(f"STORY-001: copy masked lines {number}", output)
        self.assertNotIn(NAME, output)
        self.assertEqual("pull-request", self.step())
        self.assertFalse(re.search(r"/home/", self.git(self.product, "show", "devteam/STORY-001:docs/work-items/STORY-001.md")))
        again = self.devteam("backlog", "capture", "story", "Copy", "--file", self.write_body(copy.split("\n---\n", 1)[1]),
                             "--parent", "EPIC-001")
        self.assertNotIn("masked", again.stdout)

    def write_body(self, text):
        path = self.base / "body.md"
        path.write_text(text)
        return str(path)


class TestBacklogCommits(Product):
    """Nothing tripping reaches a commit on the backlog branch, whichever route makes the commit."""

    def setUp(self):
        super().setUp()
        self.move("analyse")

    def leak(self, target="stories/STORY-001.md", line=None):
        line = line or f"Leaked: {HOME}/src/thing.py"
        return f"printf '\\n%s\\n' '{line}' >> \"$BACKLOG/{target}\""

    def assert_saved_unmasked(self, item="STORY-001"):
        [saved] = self.saved(item)
        self.assertIn(NAME, saved.read_text())
        return saved

    def test_a_successful_step_is_committed_masked_with_the_original_saved(self):
        self.plan({"sh": self.leak(), "reply": "analysed"})
        output = self.run_once()
        self.assertEqual("challenge", self.step())
        self.assertIn("STORY-001: analysed -> challenge", self.subjects())
        self.assert_never_committed()
        self.assertIn("Leaked: <path>", self.text())
        saved = self.assert_saved_unmasked()
        self.assertRegex(output, rf"stories/STORY-001\.md: masked lines \d+; original saved to backlog/log/STORY-001/{saved.name}")
        self.assertNotIn(NAME, output)

    def test_an_engine_that_writes_a_path_then_exits_non_zero_commits_it_masked(self):
        self.plan({"sh": self.leak(), "reply": "analysed", "exit": 3})
        self.run_once()
        self.assertEqual("analysis", self.step())
        self.assertIn("STORY-001: analysis failed", self.subjects())
        self.assert_never_committed()
        self.assert_saved_unmasked()

    def test_a_path_written_to_a_different_item_is_masked_in_the_commit(self):
        self.devteam("backlog", "capture", "story", "Other", "--id", "STORY-002", "--parent", "EPIC-001")
        self.plan({"sh": self.leak("stories/STORY-002.md"), "reply": "analysed"})
        self.run_once()
        self.assert_never_committed()
        self.assertIn("Leaked: <path>", self.text(self.backlog / "stories" / "STORY-002.md"))
        self.assert_saved_unmasked("STORY-002")
        self.assertEqual([], self.saved("STORY-001"))

    def test_an_item_captured_by_another_process_while_the_engine_runs_commits_nothing_tripping(self):
        capture = (f'printf "Body\\n" > "$BACKLOG/../second.md"; PYTHONPATH="$ROOT" $DEVTEAM backlog capture story '
                   f'Second --id STORY-002 --parent EPIC-001 --file "$BACKLOG/../second.md" > "$BACKLOG/../capture.out" 2>&1')
        self.plan({"sh": f"{self.leak()}; {capture}", "reply": "analysed"})
        self.run_once()
        self.assertIn("STORY-002: captured at captured", self.subjects())
        self.assert_never_committed()
        self.assert_saved_unmasked()
        notice = (self.product / "capture.out").read_text()
        self.assertIn("masked lines", notice)
        self.assertIn("backlog/log/STORY-001/unmasked-", notice)
        self.assertNotIn(NAME, notice)

    def test_a_non_markdown_file_beside_the_item_and_a_file_in_the_backlog_root_are_masked(self):
        sh = f"{self.leak('stories/notes.txt')}; {self.leak('brief.md', f'cwd={HOME}/work')}"
        self.plan({"sh": sh, "reply": "analysed"})
        self.run_once()
        self.assert_never_committed()
        self.assertIn("Leaked: <path>", (self.backlog / "stories" / "notes.txt").read_text())
        self.assertIn("cwd=<path>", (self.backlog / "brief.md").read_text())
        unmasked = {path.name.split("-", 1)[1]: path for path in (self.backlog / "log" / "unmasked").iterdir()}
        self.assertEqual({"stories__notes.txt", "brief.md"}, set(unmasked))
        for path in unmasked.values():
            self.assertIn(NAME, path.read_text())
        self.assertEqual("challenge", self.step())

    def test_an_item_with_broken_front_matter_is_masked_and_saved_under_its_file_stem(self):
        damage = "sed -i 's/^title: Story/title: Changed/' \"$BACKLOG/stories/STORY-001.md\""
        self.plan({"sh": f"{damage}; {self.leak()}", "reply": "analysed"})
        output = self.run_once()
        self.assertIn("front matter", output)
        self.assertEqual("analysis", self.step())
        self.assertIn("title: Changed", self.text())
        self.assert_never_committed()
        self.assert_saved_unmasked("STORY-001")

    def test_front_matter_is_never_checked_or_altered(self):
        sh = f"sed -i 's|^title: Story|title: Story {HOME}/x|' \"$BACKLOG/stories/STORY-001.md\""
        self.plan({"sh": sh, "reply": "analysed", "exit": 3})
        self.run_once()
        self.assertIn(f"title: Story {HOME}/x", self.text())
        self.assertEqual([], self.saved())

    def test_capturing_a_tripping_body_with_a_file_tells_the_caller_and_commits_it_masked(self):
        body = self.base / "tripping.md"
        body.write_text(f"Intro\n\nWorked in {self.product}/src and {HOME}/other too.\n")
        result = self.devteam("backlog", "capture", "story", "Third", "--id", "STORY-003", "--parent", "EPIC-001",
                              "--file", str(body))
        self.assertRegex(result.stdout, r"stories/STORY-003\.md: masked lines \d+; original saved to "
                                        r"backlog/log/STORY-003/unmasked-\S+\.md")
        self.assertNotIn(NAME, result.stdout)
        committed = self.git(self.backlog, "show", "devteam-backlog:stories/STORY-003.md")
        self.assertIn("Worked in src and <path> too.", committed)
        self.assert_never_committed()
        self.assertIn(NAME, self.saved("STORY-003")[0].read_text())

    def test_nothing_tripping_writes_no_unmasked_file(self):
        self.plan({"sh": self.leak(line="Plain text and src/root/app.py"), "reply": "analysed"})
        output = self.run_once()
        self.assertEqual([], self.saved())
        self.assertFalse((self.backlog / "log" / "unmasked").exists())
        self.assertNotIn("masked", output)

    def test_lines_already_committed_are_not_masked_again(self):
        with self.item.open("a") as fh:
            fh.write(f"\nOld: {HOME}/old\n")
        self.git(self.backlog, "add", "-A")
        self.git(self.backlog, "commit", "-q", "-m", "earlier record")
        self.plan({"sh": self.leak(line="New text"), "reply": "analysed"})
        self.run_once()
        self.assertEqual("challenge", self.step())
        self.assertIn(f"Old: {HOME}/old", self.text())
        self.assertEqual([], self.saved())

    def test_pull_request_feedback_with_a_home_path_is_masked_like_any_other_text(self):
        self.write_pull_request_item()
        fixtures = self.base / "gh-fixtures"
        shutil.copytree(FIXTURES, fixtures)
        (fixtures / "conversation.json").write_text(json.dumps(
            [{"user": {"login": "carol"}, "created_at": "2026-03-02T10:00:00Z",
              "body": f"Traceback in {HOME}/product/app.py line 3"}]))
        self.move(*TO_PULL_REQUEST[1:])
        self.devteam("backlog", "move", "STORY-001", "rejected")
        output = self.devteam("run", "--once", GH_STUB_FIXTURES=str(fixtures))
        text = self.text()
        self.assertIn("Traceback in <path> line 3", text)
        self.assertNotIn(NAME, text)
        self.assert_never_committed()
        self.assert_saved_unmasked()
        self.assertIn("masked lines", output.stdout)

    def write_pull_request_item(self):
        self.item.write_text(self.text() + "\n## Pull request\n\nhttps://github.com/acme/product/pull/2\n")
        self.git(self.backlog, "add", "-A")
        self.git(self.backlog, "commit", "-q", "-m", "record pull request")


class TestCopyGuardRule(Product):
    """The match rule, driven through `backlog capture --file` on a body of every shape."""

    def setUp(self):
        super().setUp()
        self.checkout = str(self.product)
        self.tripping = [
            (f"Full output: {self.checkout}/backlog/log/check/run.log", "Full output: backlog/log/check/run.log"),
            (f"The checkout {self.checkout} is clean", "The checkout . is clean"),
            (f"see {self.checkout}/src/app.py here", "see src/app.py here"),
            (f"`{HOME}/project`", "`<path>`"),
            (f"cwd={HOME}/project", "cwd=<path>"),
            (f"/root/{NAME}/project", "<path>"),
            (f"> {HOME}/project", "> <path>"),
            (f"a,{HOME}/project", "a,<path>"),
            (f"[{HOME}/project]", "[<path>]"),
            (f"a|{HOME}/project", "a|<path>"),
            (f"me@{HOME}/project", "me@<path>"),
            (f"file://{HOME}/project", "file://<path>"),
            (f"2>{HOME}/err.txt", "2><path>"),
            (f"(see {HOME}/project)", "(see <path>)"),
            (f"\"{HOME}/project\"", "\"<path>\""),
            (f"/Users/{NAME}/project", "<path>"),
            (f"/tmp/pytest-of-{NAME}/pytest-0/test_x0", "<path>"),
            (f"Interpreter: {sys.executable}", "Interpreter: <path>"),
            (f"harness at {ROOT}/devteam", "harness at <path>"),
            (f"GET {HOME}", "GET <path>"),
            (f"GET /Users/{NAME}", "GET <path>"),
        ]
        self.clean = ["src/root/app.py", "tests/root_test.py", "templates/home/index.html",
                      "https://example.com/home/news", "#!/usr/bin/env python", "/dev/null",
                      "Example /home/<name>", "Example /Users/<name>", "Example /root", "Example /home/",
                      "GET /api/orders", "/media/index.html", f"x{self.checkout}/a"]

    def capture(self, lines, item="STORY-002"):
        body = self.base / "table.md"
        body.write_text("\n".join(lines) + "\n")
        return self.devteam("backlog", "capture", "story", "Table", "--id", item, "--parent", "EPIC-001", "--file", str(body))

    def committed_lines(self, item="STORY-002"):
        return self.git(self.backlog, "show", f"devteam-backlog:stories/{item}.md").split("\n---\n", 1)[1].splitlines()

    def test_every_shape_of_machine_path_is_masked_and_the_surrounding_text_survives(self):
        sources = [source for source, _ in self.tripping]
        self.capture(["Prose before."] + sources + ["Prose after."])
        lines = self.committed_lines()
        masked = [expected for _, expected in self.tripping]
        self.assertEqual(["Prose before."] + masked + ["Prose after."], [line for line in lines if line])
        for expected in masked:
            self.assertNotIn(NAME, expected)
        self.assert_never_committed(NAME, self.checkout + "/", sys.executable)

    def test_masked_lines_trip_nothing_when_captured_again(self):
        self.capture([source for source, _ in self.tripping])
        again = self.capture(self.committed_lines(), item="STORY-003")
        self.assertNotIn("masked", again.stdout)
        self.assertEqual(self.committed_lines("STORY-002"), self.committed_lines("STORY-003"))

    def test_lines_that_are_not_machine_paths_are_left_alone(self):
        result = self.capture(self.clean)
        self.assertNotIn("masked", result.stdout)
        self.assertEqual(self.clean, [line for line in self.committed_lines() if line])
        self.assertEqual([], self.saved("STORY-002"))

    def test_the_notice_names_the_lines_that_tripped_and_not_their_content(self):
        result = self.capture(["clean", self.tripping[3][0], "clean", self.tripping[4][0]])
        [saved] = self.saved("STORY-002")
        numbers = [number for number, line in enumerate(saved.read_text().splitlines(), 1) if NAME in line]
        self.assertIn(f"masked lines {', '.join(map(str, numbers))};", result.stdout)
        self.assertNotIn(NAME, result.stdout)

    def test_this_stories_criteria_fixture_trips_nothing(self):
        body = (ROOT / "tests/fixtures/evidence/STORY-014-criteria.md").read_text()
        result = self.capture(body.splitlines(), item="STORY-014")
        self.assertNotIn("masked", result.stdout)
        self.assertEqual(body.splitlines(), self.committed_lines("STORY-014"))


class TestRecordsAlreadyCompleted(unittest.TestCase):
    def test_records_that_existed_before_this_story_are_unchanged(self):
        def git(*args):
            return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
        if git("rev-parse", "--verify", "-q", "main").returncode:
            self.skipTest("no main branch to compare with")
        changes = git("diff", "--name-status", "main", "--", "docs/work-items").stdout.splitlines()
        self.assertEqual([], [line for line in changes if not line.startswith("A")])


class TestTerminalNotification(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.product = base / "product"
        env = {**IDENTITY, **ISOLATED_GIT}
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.product)], check=True, env={**os.environ, **env})
        (self.product / "app.txt").write_text("v1\n")
        with unittest.mock.patch.dict(os.environ, env):
            repo_git.commit_all(self.product, "init")
            backlog = repo_git.ensure_backlog(self.product)
            workflows = base / "workflows"
            workflows.mkdir()
            (workflows / "default.json").write_text(json.dumps({
                "initial": "captured",
                "steps": {"captured": {"owner": "human", "transitions": {"analyse": "analysis"}},
                          "analysis": {"owner": "agent:analyst", "transitions": {"ready": "done"}},
                          "done": {"owner": "human", "transitions": {}}}}))
            self.repo = Repository(backlog, workflows, {"analyst"}, guard=PathGuard(self.product))
            self.story = self.repo.create("story", "Story", parent=self.repo.create("epic", "Epic").id)
            self.repo.transition(self.story.id, "analyse")
        self.backlog = backlog
        role = Role("analyst", "fake", "m", 5, ["fake"], "w")
        self.runner = Runner(Repository(backlog, workflows, {"analyst": role}, guard=PathGuard(self.product)),
                             {"analyst": role}, lambda *args, **kwargs: (97, ""), lambda message: None)

    async def test_a_typed_note_with_a_home_path_is_masked_and_the_customer_is_told(self):
        env = {**IDENTITY, **ISOLATED_GIT}
        with unittest.mock.patch.dict(os.environ, env):
            app = tui.Backlog(self.repo, self.runner)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                tree = app.query_one(Tree)
                pending = list(tree.root.children)
                nodes = []
                while pending:
                    node = pending.pop()
                    nodes.append(node)
                    pending.extend(node.children)
                tree.move_cursor(next(n for n in nodes if n.data.key == self.story.id))
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                self.assertIsInstance(app.screen, tui.Note)
                app.screen.query_one(TextArea).text = f"Look in {HOME}/work for it"
                await pilot.press("ctrl+s")
                await pilot.pause()
                messages = [notification.message for notification in app._notifications]
        self.assertTrue(any("masked lines" in message and "backlog/log/STORY-001/unmasked-" in message
                            for message in messages), messages)
        self.assertFalse(any(NAME in message for message in messages))
        history = subprocess.run(["git", "log", "-p", "devteam-backlog"], cwd=self.backlog, capture_output=True,
                                 text=True).stdout
        self.assertNotIn(NAME, history)
        self.assertIn("Look in <path> for it", (self.backlog / "stories" / "STORY-001.md").read_text())


if __name__ == "__main__":
    unittest.main()
