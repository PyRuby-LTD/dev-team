"""STORY-006: the team launches from any product directory, driven through the documented command line."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from argparse import Namespace
from types import SimpleNamespace

from textual.widgets import Tree

from devteam import config, tui
from devteam.backlog import Repository
from devteam.cli import locate
from devteam.runner import Runner, render

ROOT = Path(__file__).resolve().parents[1]
STUBS = ROOT / "tests" / "stubs"
STREAMS = ROOT / "tests" / "fixtures" / "streams"
LAUNCHER = ["uv", "run", "--project", str(ROOT), "python", "-P", "-m", "devteam"]
BARE_COMMAND = "uv run python -m devteam"
HARNESS_COMMAND = f"uv run --project {ROOT} python -P -m devteam"
IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
ISOLATED_GIT = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
GITHUB_FORMS = ["git@github.com:o/r.git", "https://github.com/o/r", "ssh://git@github.com/o/r.git"]
# Enough of a system for uv and git to work while hiding claude, codex and gh.
ESSENTIALS = ["uv", "git", "sh", "env", "make"]


def git(directory, *args, check=True, env=None):
    return subprocess.run(["git", *args], cwd=directory, env={**os.environ, **IDENTITY, **ISOLATED_GIT, **(env or {})},
                          capture_output=True, text=True, check=check)


def out(directory, *args, **kwargs):
    return git(directory, *args, **kwargs).stdout.strip()


def make_bin(directory, tools, stubs=()):
    """A directory of symlinks to real tools and executable no-op stand-ins."""
    directory.mkdir(exist_ok=True)
    for tool in tools:
        found = shutil.which(tool)
        if found and not (directory / tool).exists():
            (directory / tool).symlink_to(found)
    for name in stubs:
        path = directory / name
        path.write_text("#!/bin/sh\nexit 0\n")
        path.chmod(0o755)
    return directory


class Launcher(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.stubs = make_bin(self.base / "stubs", ESSENTIALS, ("claude", "codex", "gh"))
        self.counter = 0

    def env(self, **extra):
        return {**os.environ, **IDENTITY, **ISOLATED_GIT, **extra}

    def dev_team(self, *args, cwd, env=None, path=None, launcher=LAUNCHER):
        env = self.env(**(env or {}))
        if path is not None:
            env["PATH"] = str(path)
        return subprocess.run([*launcher, *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=120)

    def repo(self, name="product", commits=0, branch="main"):
        path = self.base / name
        path.mkdir()
        git(path, "init", "-q", "-b", branch)
        for number in range(commits):
            (path / f"file{number}.txt").write_text(str(number))
            git(path, "add", "-A")
            git(path, "commit", "-q", "-m", f"commit {number}")
        return path

    def with_origin(self, product, url="git@github.com:o/r.git", bare=None):
        """A GitHub-looking origin that git quietly redirects to a local bare repository."""
        bare = bare or self.base / f"{product.name}-remote.git"
        if not bare.exists():
            git(self.base, "init", "-q", "--bare", "-b", "main", str(bare))
        git(product, "remote", "add", "origin", url)
        git(product, "config", f"url.{bare}.insteadOf", url)
        return bare

    def refs(self, bare):
        return out(bare, "for-each-ref", "--format=%(refname) %(objectname)")

    def state(self, product):
        return {
            "status": out(product, "status", "--porcelain"),
            "files": sorted(p.name for p in product.iterdir() if p.name != ".git"),
            "log": out(product, "log", "--format=%H", check=False) if git(product, "rev-parse", "--verify", "-q", "HEAD", check=False).returncode == 0 else "",
        }

    def capture_story(self, product, item="STORY-001"):
        for args in (("epic", "Epic", "--id", "EPIC-001"), ("story", "Story", "--id", item, "--parent", "EPIC-001")):
            made = self.dev_team("backlog", "capture", *args, cwd=product)
            self.assertEqual(0, made.returncode, made.stderr)

    def listing(self, product):
        return self.dev_team("backlog", "list", cwd=product)


class ShadowingAndEntryPoint(Launcher):
    def test_product_modules_cannot_shadow_what_the_harness_imports(self):
        product = self.repo()
        (product / "yaml.py").write_text('raise SystemExit("shadowed")\n')
        with_flag = self.dev_team("backlog", "list", cwd=product)
        self.assertEqual(0, with_flag.returncode, with_flag.stderr)
        self.assertNotIn("shadowed", with_flag.stdout + with_flag.stderr)
        without_flag = self.dev_team("backlog", "list", cwd=product, launcher=[c for c in LAUNCHER if c != "-P"])
        self.assertIn("shadowed", without_flag.stdout + without_flag.stderr)

    def test_launcher_from_a_product_outside_the_checkout_acts_on_that_products_backlog(self):
        product = self.repo()
        self.capture_story(product, "STORY-777")
        listed = self.listing(product)
        self.assertEqual(0, listed.returncode, listed.stderr)
        self.assertIn("STORY-777", listed.stdout)
        self.assertTrue((product / "backlog" / "stories" / "STORY-777.md").is_file())
        self.assertFalse((ROOT / "backlog" / "stories" / "STORY-777.md").exists())

    def test_help_lists_every_command_and_backlog_action(self):
        result = self.dev_team("help", cwd=self.repo())
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("--product", result.stdout)
        lines = result.stdout.splitlines()
        for command in ("init", "help", "tui", "check", "backlog", "run"):
            with self.subTest(command=command):
                described = [line for line in lines if line.strip().startswith(command + " ")
                             and len(line.strip()) > len(command) + 1]
                self.assertTrue(described, f"no described entry for {command}")
        for action in ("validate", "list", "capture", "move"):
            with self.subTest(action=action):
                self.assertRegex(result.stdout, rf"(?m)^\s+{action}\s+\S")

    def test_no_arguments_exits_nonzero(self):
        result = self.dev_team(cwd=self.repo())
        self.assertNotEqual(0, result.returncode)

    def test_locate_finds_the_product_backlog_while_harness_files_stay_in_the_checkout(self):
        product = self.repo()
        top, backlog = locate(Namespace(product=str(product)))
        self.assertEqual(product, top)
        self.assertEqual(product / "backlog", backlog)
        for path in (config.ROOT / "workflows" / "default.json", config.ROOT / "config" / "roles.toml",
                     config.ROOT / "roles" / "tester.md", config.ROOT / "prompts" / "test.md"):
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file())
                self.assertEqual(ROOT, config.ROOT)
                self.assertNotIn(product, path.parents)


class EmptyRepository(Launcher):
    def test_tui_opens_an_empty_backlog_and_starts_no_agent(self):
        product = self.repo()
        calls = []
        checkout, backlog = locate(Namespace(product=str(product)))
        repo = Repository(backlog)
        runner = Runner(repo, checkout=checkout, engine=lambda *a, **k: calls.append(a) or (0, ""),
                        report=calls.append)

        async def drive():
            app = tui.Backlog(repo, runner)
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                self.assertEqual(0, len(app.query_one("#items", Tree).root.children))

        asyncio.run(drive())
        self.assertEqual([], calls)
        self.assertEqual({}, runner.runs)
        self.assertIsNone(runner.active)


class Isolation(Launcher):
    def test_changing_items_in_one_product_leaves_the_other_and_the_checkout_alone(self):
        used, other = self.repo("used"), self.repo("other", commits=1)
        git(other, "config", "user.name", "t")
        checkout_before = out(ROOT, "status", "--porcelain")
        self.dev_team("backlog", "list", cwd=other)
        other_before = self.state(other)
        other_backlog = sorted(str(p.relative_to(other)) for p in (other / "backlog").rglob("*") if ".git" not in p.parts)
        self.capture_story(used)
        result = self.dev_team("backlog", "move", "STORY-001", "analyse", cwd=used)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(other_before, self.state(other))
        self.assertEqual(other_backlog, sorted(str(p.relative_to(other)) for p in (other / "backlog").rglob("*")
                                               if ".git" not in p.parts))
        self.assertEqual(checkout_before, out(ROOT, "status", "--porcelain"))
        self.assertEqual("", out(used, "status", "--porcelain"))


class EngineFailure(Launcher):
    def story_at_analysis(self):
        product = self.repo(commits=1)
        self.capture_story(product)
        self.dev_team("backlog", "move", "STORY-001", "analyse", cwd=product)
        return product

    def step(self, product):
        return next(line.split()[1] for line in self.listing(product).stdout.splitlines() if line.startswith("STORY-001"))

    def assert_failure_leaves_item(self, product, result):
        self.assertIn("FAILED", result.stdout)
        self.assertRegex(result.stdout, r"see \S+/log/STORY-001/analysis-\S+\.log")
        self.assertEqual("analysis", self.step(product))
        self.assertEqual(0, self.listing(product).returncode)

    def test_missing_engine_command_is_reported_and_the_item_stays_put(self):
        product = self.story_at_analysis()
        result = self.dev_team("run", "--once", cwd=product, path=make_bin(self.base / "bare", ESSENTIALS))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assert_failure_leaves_item(product, result)
        log = next((product / "backlog" / "log" / "STORY-001").glob("analysis-*.log")).read_text()
        self.assertIn("could not start claude", log)

    def test_engine_exiting_nonzero_is_reported_and_the_item_stays_put(self):
        product = self.story_at_analysis()
        bin_dir = make_bin(self.base / "failing", ESSENTIALS)
        shutil.copy(STUBS / "claude", bin_dir / "claude")
        (bin_dir / "claude").chmod(0o755)
        env = {"STUB_ARGV": str(self.base / "argv.json"), "STUB_STDOUT": str(STREAMS / "nonzero.jsonl"), "STUB_CODE": "3"}
        env["PATH"] = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"
        result = subprocess.run([*LAUNCHER, "run", "--once"], cwd=product, env=self.env(**env),
                                capture_output=True, text=True, timeout=120)
        self.assert_failure_leaves_item(product, result)


class AgentsReachTheHarness(Launcher):
    def test_allow_list_names_the_checkout_command_and_never_the_bare_one(self):
        product = self.repo(commits=1)
        self.capture_story(product)
        self.dev_team("backlog", "move", "STORY-001", "analyse", cwd=product)
        bin_dir = make_bin(self.base / "claude-bin", ESSENTIALS)
        shutil.copy(STUBS / "claude", bin_dir / "claude")
        (bin_dir / "claude").chmod(0o755)
        argv_file = self.base / "argv.json"
        env = {"STUB_ARGV": str(argv_file), "STUB_STDOUT": str(STREAMS / "success.jsonl"),
               "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
        result = subprocess.run([*LAUNCHER, "run", "--once"], cwd=product, env=self.env(**env),
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(0, result.returncode, result.stderr)
        argv = json.loads(argv_file.read_text())
        allowed = argv[argv.index("--allowedTools") + 1]
        self.assertIn(f"Bash({HARNESS_COMMAND} *)", allowed)
        self.assertNotIn(f"Bash({BARE_COMMAND} *)", allowed)
        self.assertNotIn("{harness_command}", " ".join(argv))

    def test_prompts_and_tester_brief_carry_the_checkout_command(self):
        for workflow, step in (("default", "test"), ("default", "review"), ("analysis", "product-owner")):
            with self.subTest(prompt=step):
                text = render(SimpleNamespace(name=step), {}, workflow)
                self.assertIn(HARNESS_COMMAND, text)
                self.assertNotIn(BARE_COMMAND, text)
                self.assertNotIn("{{harness_command}}", text)
        brief = config.load_roles()["tester"].brief()
        self.assertIn(HARNESS_COMMAND, brief)
        self.assertNotIn(BARE_COMMAND, brief)

    def test_implement_step_hands_the_agent_judgement_led_unit_testing_and_targeted_runs(self):
        prompt = render(SimpleNamespace(name="implement"), {"verify_log": "none"}, "default")
        delivered = " ".join((config.load_roles()["implementer"].brief() + " " + prompt).split())
        for expected in (
            "main author of tests for acceptance criteria",
            "needs no unit test",
            "Prose changes",
            "adding an assertion to an existing test",
            "not the full test suite",
            "re-run any test named in findings",
            "The full suite is run later",
            "linters, type checks and builds",
            "has no test and why",
            "tester's narrative tests",
            "Run your unit tests directly",
        ):
            self.assertIn(expected, delivered)
        for gone in ("relaxed approach to unit tests", "is the automation tester's job",
                     "Run whatever tests or checks the project provides"):
            self.assertNotIn(gone, delivered)

    def test_harness_command_runs_from_a_product_directory(self):
        result = subprocess.run([*HARNESS_COMMAND.split(), "help"], cwd=self.repo(), env=self.env(),
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_no_checked_in_file_shows_the_bare_command(self):
        result = subprocess.run(["git", "grep", "-n", BARE_COMMAND, "--", "prompts", "roles", "config", "docs",
                                 ":!docs/work-items"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual("", result.stdout)

    def test_a_checkout_path_the_allow_list_cannot_carry_is_refused_at_launch(self):
        # Run the real entry point from a copy of the package whose path contains a space.
        spaced = self.base / "with space"
        spaced.mkdir()
        shutil.copytree(ROOT / "devteam", spaced / "devteam", ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("config", "roles", "prompts", "workflows"):
            shutil.copytree(ROOT / name, spaced / name)
        product = self.repo()
        python = ROOT / ".venv" / "bin" / "python"
        env = self.env(PYTHONPATH=str(spaced))
        for command in ("run", "tui", "init"):
            with self.subTest(command=command):
                result = subprocess.run([str(python), "-P", "-m", "devteam", command], cwd=product, env=env,
                                        capture_output=True, text=True, timeout=60)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("Harness checkout path", result.stderr)
        result = subprocess.run([str(python), "-P", "-m", "devteam", "help"], cwd=product, env=env,
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(0, result.returncode, result.stderr)


class Init(Launcher):
    def init(self, product, **kwargs):
        kwargs.setdefault("path", None)
        return self.dev_team("init", cwd=product, **kwargs)

    def assert_set_up(self, product, bare, branch="main"):
        make = subprocess.run(["make", "regression"], cwd=product, capture_output=True, text=True)
        self.assertNotEqual(0, make.returncode)
        self.assertIn("unimplemented", make.stdout + make.stderr)
        self.assertEqual("1", out(product, "rev-list", "--count", "HEAD"))
        self.assertEqual("Makefile", out(product, "ls-tree", "--name-only", "HEAD"))
        self.assertEqual(out(product, "rev-parse", "HEAD"), out(bare, "rev-parse", f"refs/heads/{branch}"))
        self.assertTrue((product / "backlog" / ".git").exists())

    def assert_takes_a_resolvable_base(self, product):
        checkout, backlog = locate(Namespace(product=str(product)))
        repo = Repository(backlog)
        epic = repo.create("epic", "Epic")
        record = repo.create("story", "Anything", parent=epic.id)
        os.environ.update(IDENTITY)
        try:
            Runner(repo, roles={}, checkout=checkout).take_checkout(record)
        finally:
            for key in IDENTITY:
                os.environ.pop(key, None)
        base = out(product, "config", f"branch.devteam/{record.id}.base")
        git(product, "rev-parse", "--verify", base)

    def test_init_in_an_empty_repository_commits_pushes_and_sets_up_the_backlog(self):
        product = self.repo()
        bare = self.with_origin(product)
        result = self.init(product)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("main", result.stdout)
        self.assert_set_up(product, bare)
        self.assert_takes_a_resolvable_base(product)

    def test_second_init_changes_nothing_and_says_the_product_is_already_set_up(self):
        product = self.repo()
        bare = self.with_origin(product)
        self.init(product)
        before = (out(product, "status", "--porcelain"), out(product, "log"), self.refs(bare),
                  out(product / "backlog", "log"))
        result = self.init(product)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, (out(product, "status", "--porcelain"), out(product, "log"), self.refs(bare),
                                  out(product / "backlog", "log")))
        self.assertIn("already set up", result.stdout)
        self.assertNotIn("Wire up", result.stdout)
        self.assertNotIn("WARNING", result.stdout + result.stderr)

    def test_init_after_an_earlier_launch_reaches_the_same_end_state(self):
        product = self.repo()
        bare = self.with_origin(product)
        self.assertEqual(0, self.listing(product).returncode)
        self.assertEqual(0, self.init(product).returncode)
        self.assert_set_up(product, bare)
        self.assert_takes_a_resolvable_base(product)

    def test_init_accepts_every_github_origin_form(self):
        for number, url in enumerate(GITHUB_FORMS):
            with self.subTest(url=url):
                product = self.repo(f"product{number}")
                bare = self.with_origin(product, url)
                result = self.init(product)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assert_set_up(product, bare)

    def test_init_refuses_a_look_alike_host_and_changes_nothing(self):
        product = self.repo()
        self.with_origin(product, "https://github.com.example.com/o/r.git")
        self.assert_refused(product)

    def test_init_warns_about_each_missing_command_and_still_succeeds(self):
        for missing in ("gh", "claude", "codex"):
            with self.subTest(missing=missing):
                product = self.repo(f"product-{missing}")
                self.with_origin(product)
                present = [n for n in ("claude", "codex", "gh") if n != missing]
                path = make_bin(self.base / f"path-{missing}", ESSENTIALS, present)
                result = self.init(product, path=path)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn(missing, result.stdout + result.stderr)
                for name in present:
                    self.assertNotIn(f"{name} is missing", result.stdout + result.stderr)

    def assert_refused(self, product, expect=None):
        before = self.state(product)
        before_count = before["log"]
        result = self.init(product)
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertEqual(before, self.state(product))
        self.assertEqual(before_count, self.state(product)["log"])
        self.assertFalse((product / "backlog").exists())
        self.assertFalse((product / "Makefile").exists())
        if expect:
            self.assertIn(expect, result.stdout + result.stderr)

    def test_init_refuses_outside_a_git_repository_and_creates_nothing(self):
        directory = self.base / "plain"
        directory.mkdir()
        result = self.init(directory)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual([], list(directory.iterdir()))

    def test_init_refuses_without_an_origin(self):
        self.assert_refused(self.repo())

    def test_init_refuses_an_origin_that_is_not_github(self):
        product = self.repo()
        git(product, "remote", "add", "origin", "https://example.com/o/r.git")
        self.assert_refused(product)

    def test_init_refuses_on_an_item_branch(self):
        product = self.repo(commits=1)
        self.with_origin(product)
        git(product, "switch", "-q", "-c", "devteam/STORY-001")
        self.assert_refused(product, "devteam/STORY-001")

    def test_init_refuses_a_detached_head(self):
        product = self.repo(commits=1)
        self.with_origin(product)
        git(product, "checkout", "-q", "--detach")
        self.assert_refused(product)

    def test_init_leaves_a_tracked_makefile_alone_and_warns_when_it_has_no_regression_target(self):
        product = self.repo()
        bare = self.with_origin(product)
        (product / "Makefile").write_text("build:\n\ttrue\n")
        git(product, "add", "Makefile")
        git(product, "commit", "-q", "-m", "Makefile")
        head = out(product, "rev-parse", "HEAD")
        result = self.init(product)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("regression", result.stdout + result.stderr)
        self.assertIn("WARNING", result.stdout + result.stderr)
        self.assertEqual("build:\n\ttrue\n", (product / "Makefile").read_text())
        self.assertEqual(head, out(product, "rev-parse", "HEAD"))
        self.assertEqual("1", out(product, "rev-list", "--count", "HEAD"))
        self.assertEqual(head, out(bare, "rev-parse", "refs/heads/main"))

    def test_init_commits_an_existing_untracked_makefile_unchanged_in_an_empty_repository(self):
        product = self.repo()
        bare = self.with_origin(product)
        (product / "Makefile").write_text("regression:\n\ttrue\n")
        (product / "notes.txt").write_text("not mine to commit")
        result = self.init(product)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("regression:\n\ttrue\n", (product / "Makefile").read_text())
        self.assertEqual("Makefile", out(product, "ls-tree", "--name-only", "HEAD"))
        self.assertEqual("?? notes.txt", out(product, "status", "--porcelain"))
        self.assertEqual(out(product, "rev-parse", "HEAD"), out(bare, "rev-parse", "refs/heads/main"))

    def test_init_leaves_an_untracked_makefile_untracked_in_a_repository_with_commits(self):
        product = self.repo(commits=2)
        bare = self.with_origin(product)
        (product / "Makefile").write_text("regression:\n\ttrue\n")
        head = out(product, "rev-parse", "HEAD")
        result = self.init(product)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("regression:\n\ttrue\n", (product / "Makefile").read_text())
        self.assertEqual(head, out(product, "rev-parse", "HEAD"))
        self.assertEqual("?? Makefile", out(product, "status", "--porcelain"))
        self.assertEqual("", self.refs(bare))

    def test_init_without_a_git_identity_fails_then_a_rerun_completes(self):
        product = self.repo()
        bare = self.with_origin(product)
        git(product, "config", "user.useConfigOnly", "true")
        env = {k: v for k, v in self.env().items() if k not in IDENTITY}
        failed = subprocess.run([*LAUNCHER, "init"], cwd=product, env=env, capture_output=True, text=True, timeout=120)
        self.assertNotEqual(0, failed.returncode)
        self.assertRegex(failed.stderr + failed.stdout, r"(?i)identity|user\.(name|email)|tell me who you are")
        self.assertTrue((product / "Makefile").exists())
        self.assertEqual("", self.refs(bare))
        git(product, "config", "user.name", "t")
        git(product, "config", "user.email", "t@t")
        again = self.init(product)
        self.assertEqual(0, again.returncode, again.stderr)
        self.assert_set_up(product, bare)

    def test_init_with_an_unreachable_origin_fails_after_committing_then_a_rerun_pushes(self):
        product = self.repo()
        missing = self.base / "later.git"
        self.with_origin(product, bare=missing)
        shutil.rmtree(missing)
        failed = self.init(product)
        self.assertNotEqual(0, failed.returncode)
        self.assertEqual("1", out(product, "rev-list", "--count", "HEAD"))
        git(self.base, "init", "-q", "--bare", "-b", "main", str(missing))
        again = self.init(product)
        self.assertEqual(0, again.returncode, again.stderr)
        self.assertEqual(out(product, "rev-parse", "HEAD"), out(missing, "rev-parse", "refs/heads/main"))
        self.assertEqual("1", out(product, "rev-list", "--count", "HEAD"))

    def test_init_in_an_existing_codebase_writes_an_uncommitted_makefile_and_pushes_nothing(self):
        product = self.repo(commits=2)
        bare = self.with_origin(product)
        head = out(product, "rev-parse", "HEAD")
        result = self.init(product)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("?? Makefile", out(product, "status", "--porcelain"))
        self.assertEqual(head, out(product, "rev-parse", "HEAD"))
        self.assertEqual("", self.refs(bare))
        self.assertTrue((product / "backlog" / ".git").exists())
        self.assertRegex(result.stdout, r"(?s)make regression.*commit.*dev-team tui")

    def test_init_does_not_push_unpushed_work(self):
        product = self.repo(commits=1)
        bare = self.with_origin(product)
        (product / "Makefile").write_text("regression:\n\ttrue\n")
        git(product, "add", "Makefile")
        git(product, "commit", "-q", "-m", "Makefile")
        git(product, "switch", "-q", "-c", "spike")
        (product / "spike.txt").write_text("x")
        git(product, "add", "-A")
        git(product, "commit", "-q", "-m", "spike")
        before = (self.refs(bare), out(product, "rev-list", "--count", "main", "spike"))
        result = self.init(product)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, (self.refs(bare), out(product, "rev-list", "--count", "main", "spike")))
        self.assertNotIn("Wire up", result.stdout)

    def test_init_does_not_push_a_main_that_is_ahead_of_origin(self):
        product = self.repo(commits=1)
        bare = self.with_origin(product)
        git(product, "push", "-q", "origin", "main")
        for name in ("a", "b", "c"):
            (product / f"{name}.txt").write_text(name)
            git(product, "add", "-A")
            git(product, "commit", "-q", "-m", name)
        (product / "Makefile").write_text("regression:\n\ttrue\n")
        git(product, "add", "Makefile")
        git(product, "commit", "-q", "-m", "Makefile")
        before = self.refs(bare)
        result = self.init(product)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, self.refs(bare))

    def test_init_warns_and_pushes_nothing_when_origin_holds_the_branch_at_another_commit(self):
        product = self.repo()
        bare = self.with_origin(product)
        other = self.repo("other", commits=1)
        git(other, "push", "-q", str(bare), "main")
        before = self.refs(bare)
        result = self.init(product)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("WARNING", result.stdout + result.stderr)
        self.assertEqual(before, self.refs(bare))
        self.assertEqual("1", out(product, "rev-list", "--count", "HEAD"))


class InstallScript(Launcher):
    def setUp(self):
        super().setUp()
        self.home = self.base / "home"
        self.home.mkdir()
        self.checkout = self.base / "checkout"
        self.checkout.mkdir()
        shutil.copy(ROOT / "install.sh", self.checkout / "install.sh")
        self.checkout_script = self.checkout / "install.sh"

    def path(self, present, name="path"):
        directory = make_bin(self.base / name, ["bash", "grep", "dirname"])
        for tool in present:
            stub = directory / tool
            if tool == "git":
                stub.write_text('#!/bin/sh\n[ "$1" = config ] && [ -n "$STUB_GIT_IDENTITY" ] && echo set\nexit 0\n')
            else:
                stub.write_text("#!/bin/sh\nexit 0\n")
            stub.chmod(0o755)
        return directory

    def install(self, present, script=None, identity=True, name="path"):
        env = {"HOME": str(self.home), "PATH": str(self.path(present, name))}
        if identity:
            env["STUB_GIT_IDENTITY"] = "1"
        return subprocess.run([shutil.which("bash"), str(script or self.checkout_script)], env=env,
                              capture_output=True, text=True, timeout=30)

    ALL = ("uv", "git", "claude", "codex", "gh")

    def test_alias_is_appended_once_and_a_rerun_warns_without_touching_the_file(self):
        first = self.install(self.ALL)
        self.assertEqual(0, first.returncode, first.stderr)
        bashrc = self.home / ".bashrc"
        content = bashrc.read_text()
        self.assertEqual(1, content.count("alias dev-team="))
        self.assertIn(f'uv run --project "{self.checkout}" python -P -m devteam', content)
        second = self.install(self.ALL)
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual(content, bashrc.read_text())
        self.assertRegex(second.stdout + second.stderr, r"(?i)warning.*already exists")

    def test_the_alias_runs_the_launcher_in_the_current_directory(self):
        installed = self.install(self.ALL, script=ROOT / "install.sh")
        self.assertEqual(0, installed.returncode, installed.stderr)
        product = self.repo()
        script = f'shopt -s expand_aliases\nsource "{self.home}/.bashrc"\ndev-team backlog capture epic Aliased --id EPIC-009'
        result = subprocess.run([shutil.which("bash"), "-c", script], cwd=product,
                                env={**self.env(), "HOME": str(self.home)}, capture_output=True, text=True, timeout=120)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((product / "backlog" / "epics" / "EPIC-009.md").is_file())

    def test_every_missing_prerequisite_is_reported_in_one_run(self):
        result = self.install(("claude",), identity=False)
        self.assertNotEqual(0, result.returncode)
        report = result.stdout + result.stderr
        for name in ("uv", "git", "codex", "gh"):
            self.assertIn(name, report)
        self.assertFalse((self.home / ".bashrc").exists())

    def test_missing_required_tool_alone_fails(self):
        for missing in ("uv", "git"):
            with self.subTest(missing=missing):
                result = self.install([t for t in self.ALL if t != missing], name=f"without-{missing}")
                self.assertNotEqual(0, result.returncode)
                self.assertIn(missing, result.stdout + result.stderr)

    def test_missing_optional_tools_or_identity_only_warn(self):
        for present, identity in ((("uv", "git", "codex", "gh"), True), (("uv", "git", "claude", "gh"), True),
                                  (("uv", "git", "claude", "codex"), True), (self.ALL, False)):
            with self.subTest(present=present, identity=identity):
                self.counter += 1
                self.home = self.base / f"home-{self.counter}"
                self.home.mkdir()
                result = self.install(present, identity=identity, name=f"opt-{self.counter}")
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("WARNING", result.stdout + result.stderr)

    def test_only_bashrc_is_written_and_the_checkout_is_untouched(self):
        before = out(ROOT, "status", "--porcelain")
        result = self.install(self.ALL)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([".bashrc"], sorted(p.name for p in self.home.iterdir()))
        self.assertEqual(before, out(ROOT, "status", "--porcelain"))
        self.assertEqual(["install.sh"], sorted(p.name for p in self.checkout.iterdir()))

    def test_checkout_paths_the_allow_list_cannot_carry_are_refused(self):
        for name in ("with space", "star*", "paren(s)"):
            with self.subTest(name=name):
                directory = self.base / name
                directory.mkdir()
                shutil.copy(ROOT / "install.sh", directory / "install.sh")
                result = self.install(self.ALL, script=directory / "install.sh", name=f"p-{len(name)}")
                self.assertNotEqual(0, result.returncode)
                self.assertTrue((result.stdout + result.stderr).strip())
                self.assertFalse((self.home / ".bashrc").exists())

    def test_script_is_valid_bash_and_executable(self):
        self.assertEqual(0, subprocess.run(["bash", "-n", str(ROOT / "install.sh")]).returncode)
        self.assertTrue((ROOT / "install.sh").stat().st_mode & stat.S_IXUSR)


class Guards(unittest.TestCase):
    def grep(self, *args):
        return subprocess.run(args, cwd=ROOT, capture_output=True, text=True).stdout

    def test_retired_workspace_mechanism_stays_gone(self):
        self.assertEqual("", self.grep("git", "grep", "-nE", "config/workspace|tools/workspace", "--", ".",
                                       ":!backlog", ":!docs", ":!tests"))

    def test_nothing_in_the_harness_reads_the_home_directory(self):
        self.assertEqual("", self.grep("grep", "-rnE", r"Path\.home|expanduser|environ\[.HOME", "devteam"))

    def test_readme_has_no_pip_or_bare_python3_and_no_bare_harness_command(self):
        self.assertEqual("", self.grep("grep", "-nE", r"\bpip\b|python3", "README.md"))
        self.assertEqual("", self.grep("git", "grep", "-n", BARE_COMMAND, "--", "README.md", "docs/backlog.md"))
        self.assertNotIn("(the workspace)", (ROOT / "README.md").read_text())


if __name__ == "__main__":
    unittest.main()
