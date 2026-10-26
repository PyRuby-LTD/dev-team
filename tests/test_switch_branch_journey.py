import unittest

from devteam import git, tui
from tests import test_checkout as fixtures


class SwitchBranchJourney(unittest.IsolatedAsyncioTestCase):
    def engine(self, role, prompt, cwd, extra_dir, log, on_line=None):
        return fixtures.CheckoutAcceptance.engine(self, role, prompt, cwd, extra_dir, log)

    steps = fixtures.CheckoutAcceptance.steps

    def setUp(self):
        fixtures.CheckoutAcceptance.setUp(self)
        self.repo.transition(self.first.id, "play")
        self.runner.run(once=True)
        self.repo.transition(self.second.id, "play")

    async def test_customer_switches_to_the_branch_of_a_story_waiting_for_review(self):
        self.assertEqual("accept", self.steps()[self.first.id])
        tip = git.must(self.product, "rev-parse", f"devteam/{self.first.id}")
        app = tui.Backlog(self.repo, self.runner)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            tree = app.query_one("#items")
            tree.move_cursor(next(n for n in tree.root.children[0].children if n.data.key == self.first.id))
            await pilot.pause()

            await pilot.press("x")
            await pilot.pause()

            self.assertEqual(f"devteam/{self.first.id}", git.current_branch(self.product))
            self.assertEqual(tip, git.must(self.product, "rev-parse", "HEAD"))
            self.assertEqual("accept", self.steps()[self.first.id])
