"""The default workflow's fourth group: review, then the customer accepts, revises or abandons the change."""
import unittest

import yaml

from devteam.redesign.work_item import parse

from .test_implement_journey import blocked, implemented
from .test_verify_journey import WRITTEN, Synced

FINDINGS = [{"location": "planner.py:12", "concern": "correctness", "finding": "A week starting on Sunday loses a day",
             "outcome": "fix"},
            {"concern": "design", "finding": "The planner and printer share a date helper", "outcome": "task",
             "task": "Extract the date helper"}]

REVISE = f"""$DEV_TEAM backlog submit STORY-001 revise <<'OUTPUT'
{yaml.safe_dump({"findings": FINDINGS})}OUTPUT
"""

APPROVE = """$DEV_TEAM backlog submit STORY-001 approve
"""


def seen_by(name):
    return (f"python3 -c 'import os, shutil; shutil.copy(\"backlog/stories/STORY-001.yaml\", "
            f"os.environ[\"STUB_PROMPTS\"] + \"/{name}\")'\n")


class ReviewAndAccept(Synced):
    def accepting(self):
        self.play(implemented("STORY-001", "planner.txt"), WRITTEN, APPROVE)
        self.ok("run", "--once")
        self.assertEqual("accept", self.story("STORY-001").step)

    def test_review_sends_findings_back_to_implement_then_approves_into_accept(self):
        self.play(implemented("STORY-001", "planner.txt"), WRITTEN, REVISE,
                  seen_by("item-seen-after-review.yaml") + implemented("STORY-001", "week.txt"), WRITTEN, APPROVE)

        self.ok("run", "--once")

        self.assertEqual("accept", self.story("STORY-001").step)
        self.assertEqual([("verify", "passed", "review"), ("review", "revise", "implement"),
                          ("implement", "implemented", "test"), ("test", "written", "sync"),
                          ("sync", "completed", "verify"), ("verify", "passed", "review"),
                          ("review", "approve", "accept")], self.history("STORY-001")[-7:])
        seen = parse((self.prompts / "item-seen-after-review.yaml").read_text())
        [review] = [entry for entry in seen.pending("implement") if entry.step == "review"]
        self.assertEqual("revise", review.outcome)
        self.assertEqual(FINDINGS, review.output["findings"])
        self.assertIn("week.txt", self.files("devteam/STORY-001"))

    def test_revising_at_accept_puts_the_customers_feedback_before_the_implementer(self):
        self.accepting()
        self.script({"sh": seen_by("item-seen-after-accept.yaml") + blocked("STORY-001")})
        for stale in self.prompts.glob("*"):
            stale.unlink()

        self.ok("backlog", "record", "STORY-001", "revise", stdin="feedback: Weeks should start on Monday.\n")
        self.ok("run", "--once")

        seen = parse((self.prompts / "item-seen-after-accept.yaml").read_text())
        self.assertEqual("implement", seen.step)
        self.assertEqual([("accept", "revise", {"feedback": "Weeks should start on Monday."})],
                         [(entry.step, entry.outcome, entry.output) for entry in seen.pending("implement")])

    def test_abandoning_returns_the_checkout_to_its_base_and_keeps_the_items_branch(self):
        self.accepting()
        tip = self.git("rev-parse", "devteam/STORY-001")

        self.ok("backlog", "record", "STORY-001", "abandon")
        self.ok("run", "--once")

        self.assertEqual("abandoned", self.story("STORY-001").step)
        self.assertEqual([("accept", "abandon", "abandoning"), ("abandoning", "completed", "abandoned")],
                         self.history("STORY-001")[-2:])
        self.assertEqual("main", self.git("branch", "--show-current").strip())
        self.assertEqual(tip, self.git("rev-parse", "devteam/STORY-001"))
        self.assertNotIn("planner.txt", self.files("HEAD"))
        self.assertEqual("", self.git("status", "--porcelain"))

    def test_the_review_prompt_is_previewable(self):
        self.script(*self.ready("STORY-001"))
        self.ok("run", "--once")
        self.assertTrue(self.ok("prompt", "review", "--item", "STORY-001").stdout.strip())


if __name__ == "__main__":
    unittest.main()
