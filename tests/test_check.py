import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from devteam import check
from devteam.console import main

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


if __name__ == "__main__":
    unittest.main()
