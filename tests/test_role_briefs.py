"""STORY-017: the analyst and challenger briefs define what is built and leave test design to others.

The briefs are read the way the harness reads them, through the configured roles; the challenge
prompt is read from the prompts directory the harness hands to the challenger.
"""
import re
import unittest

from devteam.config import ROOT, load_roles

PROMPT_VERBS = re.compile(r"\b(write|add|propose|require|specify|prescribe|include)\b[^.\n]*\btests?\b", re.I)

UNCHANGED_FRONTS = (
    "- **Unevidenced claims.** Statements about the code, the users or current\n"
    "  behaviour with no source. Check claims about the code against the repository\n"
    "  yourself.\n",
    "- **Inference presented as the customer's decision.** Anything the item treats\n"
    "  as settled that the customer did not say in their own text, their answers or\n"
    "  their feedback.\n",
    "- **Scope that serves no stated outcome.** Trace each criterion back to what the\n"
    "  customer asked for. What is left over should not be built, or points to an\n"
    "  outcome nobody wrote down.\n",
    "- **The cheapest way to be wrong.** For the riskiest assumption in the item,\n"
    "  what is the smallest thing to check or ask that would settle it?\n",
)


def flat(text):
    return " ".join(text.split())


class RoleBriefs(unittest.TestCase):
    def setUp(self):
        roles = load_roles()
        self.analyst = roles["analyst"].brief()
        self.challenger = roles["challenger"].brief()

    def test_analyst_defines_criteria_as_observable_behaviour_and_what_is_built(self):
        text = flat(self.analyst)
        self.assertIn("observable behaviour", text)
        self.assertIn("what is to be built", text)

    def test_analyst_rejects_criteria_too_vague_to_implement_and_verify(self):
        self.assertIn("too vague to be implemented and verified", flat(self.analyst))

    def test_analyst_does_not_measure_criteria_by_running_a_test(self):
        self.assertNotIn("running a test", flat(self.analyst))

    def test_analyst_leaves_test_choice_and_level_to_implementer_and_tester(self):
        text = flat(self.analyst)
        self.assertIn("does not specify which tests, or at what level", text)
        self.assertIn("implementer and tester", text)

    def test_challenger_judges_criteria_by_whether_they_can_be_implemented_and_verified(self):
        text = flat(self.challenger)
        self.assertIn("unambiguous enough to be implemented and verified", text)

    def test_challenger_does_not_measure_criteria_by_running_a_test(self):
        self.assertNotIn("running a test", flat(self.challenger))

    def test_challenger_says_it_does_not_prescribe_tests_or_their_level(self):
        text = flat(self.challenger)
        self.assertIn("does not prescribe which tests to write or at what level", text)
        self.assertIn("implementer and tester", text)

    def test_challenger_keeps_its_other_four_fronts_word_for_word(self):
        for front in UNCHANGED_FRONTS:
            with self.subTest(front=front.split("**")[1]):
                self.assertIn(front, self.challenger)
        self.assertIn("Attack the item on five fronts:", self.challenger)

    def test_challenge_prompt_does_not_tell_the_challenger_to_propose_or_require_tests(self):
        text = (ROOT / "prompts" / "challenge.md").read_text()
        self.assertIsNone(PROMPT_VERBS.search(text), PROMPT_VERBS.search(text))


if __name__ == "__main__":
    unittest.main()
