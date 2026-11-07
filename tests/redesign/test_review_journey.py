"""The default workflow's fourth group: review, then the customer accepts, revises or abandons the change."""
import unittest

import yaml

from .journey import submit
from .test_implement_journey import blocked, implemented
from .test_verify_journey import WRITTEN, Synced

FINDINGS = [{"location": "planner.py:12", "concern": "correctness", "finding": "A week starting on Sunday loses a day",
             "outcome": "fix"},
            {"concern": "design", "finding": "The planner and printer share a date helper", "outcome": "task",
             "task": "Extract the date helper"}]

REVISE = submit("revise", yaml.safe_dump({"findings": FINDINGS}))
APPROVE = submit("approve")


class ReviewAndAccept(Synced):
    def accepting(self):
        self.play(implemented("planner.txt"), WRITTEN, APPROVE)
        self.run_once()
        self.assertEqual("accept", self.story("STORY-001").step)

    def test_review_sends_findings_back_to_implement_then_approves_into_accept(self):
        self.play(implemented("planner.txt"), WRITTEN, REVISE, implemented("week.txt"), WRITTEN, APPROVE)

        self.run_once()

        self.assertEqual("accept", self.story("STORY-001").step)
        self.assertEqual([("verify", "passed", "review"), ("review", "revise", "implement"),
                          ("implement", "implemented", "test"), ("test", "written", "sync"),
                          ("sync", "completed", "verify"), ("verify", "passed", "review"),
                          ("review", "approve", "accept")], self.history("STORY-001")[-7:])
        [review] = [entry for entry in self.seen_at("implement").pending("implement") if entry.step == "review"]
        self.assertEqual("revise", review.outcome)
        self.assertEqual(FINDINGS, review.output["findings"])
        self.assertIn("week.txt", self.files("devteam/STORY-001"))

    def test_revising_at_accept_puts_the_customers_feedback_before_the_implementer(self):
        self.accepting()
        self.script(blocked)

        self.team.record("STORY-001", "revise", "feedback: Weeks should start on Monday.\n")
        self.run_once()

        seen = self.seen_at("implement")
        self.assertEqual([("accept", "revise", {"feedback": "Weeks should start on Monday."})],
                         [(entry.step, entry.outcome, entry.output) for entry in seen.pending("implement")])

    def test_abandoning_returns_the_checkout_to_its_base_and_keeps_the_items_branch(self):
        self.accepting()
        tip = self.git("rev-parse", "devteam/STORY-001")

        self.team.record("STORY-001", "abandon")
        self.run_once()

        self.assertEqual("abandoned", self.story("STORY-001").step)
        self.assertEqual([("accept", "abandon", "abandoning"), ("abandoning", "completed", "abandoned")],
                         self.history("STORY-001")[-2:])
        self.assertEqual("main", self.git("branch", "--show-current").strip())
        self.assertEqual(tip, self.git("rev-parse", "devteam/STORY-001"))
        self.assertNotIn("planner.txt", self.files("HEAD"))
        self.assertEqual("", self.git("status", "--porcelain"))

    def test_the_review_prompt_is_previewable(self):
        self.script(*self.ready("STORY-001"))
        self.run_once()
        self.previewable("review", "STORY-001")


if __name__ == "__main__":
    unittest.main()
