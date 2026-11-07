"""Launching dev-team in a product: setup is a prerequisite, and the harness brings its own workflows."""
import shutil
import unittest

from tests.redesign.test_request_journey import QUESTIONS, ROOT, Product


class ProductOutsideTheHarness(Product):
    def test_work_items_land_in_the_products_backlog_while_the_harness_brings_its_own_workflows(self):
        harness = self.base / "harness"
        for directory in ("devteam", "workflows", "prompts", "config", "roles", "standards"):
            shutil.copytree(ROOT / directory, harness / directory, ignore=shutil.ignore_patterns("__pycache__"))
        for directory in ("workflows", "config"):
            (self.product / directory).mkdir()
        (self.product / "workflows" / "request.yaml").write_text("not: [a workflow\n")
        (self.product / "config" / "roles.toml").write_text("not toml\n")
        self.script({"sh": QUESTIONS})
        environment = {"PYTHONPATH": str(harness)}

        for command, stdin in ((("backlog", "create", "request", "Plan meals"), "overview: Plan meals.\n"),
                               (("backlog", "record", "REQUEST-001", "analyse"), ""),
                               (("run", "--once"), "")):
            result = self.dev_team(*command, stdin=stdin, env=environment)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)

        self.assertEqual("answering", self.request().step)
        self.assertFalse((harness / "backlog").exists(), "the harness kept a backlog of its own")
        self.assertEqual([], list(harness.rglob("REQUEST-001*")))


class UnsetProduct(Product):
    def set_up_product(self):
        pass

    def commit_makefile(self, text):
        (self.product / "Makefile").write_text(text)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "Add a Makefile")

    def assertLaunchRefused(self):
        self.script({"sh": QUESTIONS})
        for command in (("run", "--once"), ("tui",)):
            with self.subTest(command=command):
                result = self.dev_team(*command)
                self.assertNotEqual(0, result.returncode)
                self.assertTrue(result.stderr.strip(), "nothing reported")
        self.assertFalse(self.prompts.exists(), "an engine ran")

    def test_a_product_without_a_backlog_branch_is_refused_and_launch_does_not_create_one(self):
        self.commit_makefile("regression:\n\ttrue\n")
        self.assertLaunchRefused()
        self.assertFalse(self.git("branch", "--list", "devteam-backlog").strip(), "launch set up the backlog")

    def test_a_product_without_a_regression_target_is_refused(self):
        self.commit_makefile("build:\n\ttrue\n")
        self.ok("init")
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
        self.script({"sh": QUESTIONS})
        self.ok("--product", str(self.empty), "init")
        self.ok("--product", str(self.empty), "run", "--once")
        self.assertIn("refs/heads/devteam-backlog", self.git("for-each-ref", cwd=self.empty))
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.empty),
                         self.git("rev-parse", "refs/heads/main", cwd=self.remote))

        before = self.state()
        self.ok("--product", str(self.empty), "init")
        self.assertEqual(before, self.state())


if __name__ == "__main__":
    unittest.main()
