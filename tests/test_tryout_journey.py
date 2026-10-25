import os
from pathlib import Path
import time
import unittest

from devteam import git, tui
from tests import test_checkout as fixtures


class TryoutJourney(unittest.IsolatedAsyncioTestCase):
    def engine(self, role, prompt, cwd, extra_dir, log, on_line=None):
        return fixtures.CheckoutAcceptance.engine(self, role, prompt, cwd, extra_dir, log)

    steps = fixtures.CheckoutAcceptance.steps

    def setUp(self):
        fixtures.CheckoutAcceptance.setUp(self)
        self.pidfile = Path(self.temp.name) / "product.pid"
        (self.product / "Makefile").write_text(
            f"run:\n\t@echo product ready; echo $$$$ > {self.pidfile}; exec sleep 60\n")
        git.commit_all(self.product, "add run target")
        git.must(self.product, "push", "-q", "origin", "main")
        self.repo.transition(self.first.id, "play")
        self.runner.run(once=True)

    async def settle(self, pilot, condition):
        for _ in range(200):
            await pilot.pause(0.05)
            if condition():
                return
        self.fail(f"not reached: {self.runner.tryout.status!r} {self.messages[-3:]}")

    def product_running(self):
        try:
            os.kill(int(self.pidfile.read_text()), 0)
            return True
        except (FileNotFoundError, ValueError, ProcessLookupError):
            return False

    async def test_customer_tries_out_a_story_waiting_for_review_and_releases_it(self):
        self.assertEqual("accept", self.steps()[self.first.id])
        self.repo.transition(self.second.id, "play")
        app = tui.Backlog(self.repo, self.runner)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            tree = app.query_one("#items")
            tree.move_cursor(next(n for n in tree.root.children[0].children if n.data.key == self.first.id))
            await pilot.pause()

            await pilot.press("x")
            await self.settle(pilot, self.product_running)
            self.assertEqual(f"devteam/{self.first.id}", git.current_branch(self.product))
            logs = list((self.backlog / "log" / self.first.id).glob("run-*.log"))
            await self.settle(pilot, lambda: any("product ready" in log.read_text() for log in logs))
            self.assertEqual("accept", self.steps()[self.first.id])

            await pilot.press("e")
            await self.settle(pilot, lambda: not self.product_running())

            deadline = time.monotonic() + 10
            while self.steps()[self.second.id] == "implement" and time.monotonic() < deadline:
                self.runner.run(once=True)
            self.assertNotEqual("implement", self.steps()[self.second.id], (self.messages[-4:]))
            self.assertIn("STORY-002", [call[0] for call in self.calls])
