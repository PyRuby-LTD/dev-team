"""STORY-008: agent output streams live to the run log, driven through `devteam run` with a stub claude on PATH."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
STUBS = ROOT / "tests" / "stubs"
STREAMS = ROOT / "tests" / "fixtures" / "streams"


class StreamingThroughRun(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.product = Path(self.temp.name) / "product"
        self.product.mkdir()
        self.backlog = self.product / "backlog"
        self.bin = Path(self.temp.name) / "bin"
        self.bin.mkdir()
        shutil.copy(STUBS / "claude", self.bin / "claude")
        (self.bin / "claude").chmod(0o755)
        self.devteam("backlog", "capture", "epic", "Epic", "--id", "EPIC-001")
        self.devteam("backlog", "capture", "story", "Story", "--id", "STORY-001", "--parent", "EPIC-001")
        self.devteam("backlog", "move", "STORY-001", "analyse")

    def devteam(self, *args, env=None):
        return subprocess.run([sys.executable, "-m", "devteam", "--product", str(self.product), *args],
                              cwd=ROOT, env={**os.environ, **(env or {})}, capture_output=True, text=True,
                              timeout=60, check=env is None)

    def run_agent(self, stream, stderr=None, code=0, await_log=False):
        env = {"PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
               "STUB_ARGV": str(Path(self.temp.name) / "argv.json"),
               "STUB_STDOUT": str(STREAMS / stream), "STUB_CODE": str(code)}
        if stderr:
            env["STUB_STDERR"] = str(STREAMS / stderr)
        if await_log:
            env["STUB_AWAIT_LOG"] = str(self.backlog / "log")
        return self.devteam("run", "--once", env=env)

    def step(self):
        listing = self.devteam("backlog", "list").stdout
        return next(line.split()[1] for line in listing.splitlines() if line.startswith("STORY-001"))

    def log(self):
        (path,) = (self.backlog / "log" / "STORY-001").glob("analysis-*.log")
        return path.read_text()

    def test_claude_is_invoked_with_stream_json_and_no_partial_messages(self):
        self.run_agent("success.jsonl")
        argv = json.loads((Path(self.temp.name) / "argv.json").read_text())
        index = argv.index("--output-format")
        self.assertEqual(["stream-json", "--verbose"], argv[index + 1:index + 3])
        self.assertNotIn("--include-partial-messages", argv)

    def test_result_event_is_the_reply_that_drives_the_transition(self):
        result = self.run_agent("success.jsonl")
        self.assertEqual("answering", self.step())
        self.assertIn("analysis (analyst via claude/sonnet): questions -> answering", result.stdout)

    def test_log_holds_the_raw_stream_including_stderr(self):
        self.run_agent("success.jsonl", stderr="stderr.txt")
        body = self.log()
        recorded = (STREAMS / "success.jsonl").read_text()
        self.assertIn(recorded, body.replace("warning: something on stderr\n", ""))
        self.assertIn("warning: something on stderr\n", body)

    def test_first_line_is_in_the_log_while_the_agent_is_still_running(self):
        self.run_agent("success.jsonl", await_log=True)
        self.assertEqual("answering", self.step())

    def test_assistant_text_is_the_reply_when_there_is_no_result_event(self):
        self.run_agent("no_result.jsonl")
        self.assertEqual("answering", self.step())

    def test_malformed_line_is_logged_verbatim_and_does_not_break_the_reply(self):
        self.run_agent("malformed.jsonl")
        self.assertEqual("answering", self.step())
        self.assertIn("this is not json {", self.log())

    def test_stream_without_result_or_text_fails_the_step(self):
        result = self.run_agent("empty.jsonl")
        self.assertEqual("analysis", self.step())
        self.assertIn("FAILED - exit 1", result.stdout)

    def test_non_zero_exit_code_is_kept_and_fails_the_step(self):
        result = self.run_agent("nonzero.jsonl", code=7)
        self.assertEqual("analysis", self.step())
        self.assertIn("FAILED - exit 7", result.stdout)

    def test_missing_binary_fails_the_step_with_a_logged_message(self):
        git_dir = str(Path(shutil.which("git")).parent)
        if shutil.which("claude", path=git_dir):
            self.skipTest("claude is installed next to git")
        result = self.devteam("run", "--once", env={"PATH": git_dir})
        self.assertIn("FAILED - exit 127", result.stdout)
        self.assertIn("could not start claude", self.log())


if __name__ == "__main__":
    unittest.main()
