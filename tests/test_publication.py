import unittest

from devteam.publication import requirements


class PublishedRequirements(unittest.TestCase):
    def test_keeps_preamble_and_requirements_in_item_order_with_subheadings(self):
        body = ("\nAs a customer, I want this.\n\n\n"
                "## Acceptance Criteria\n\n1. Works.\n### Detail\nKeep this detail.\n\n\n"
                "## Analysis\nWorking notes.\n### Detail\nDiscard this detail.\n\n"
                "## Context\n\nWhy it matters.\n\n\n")
        self.assertEqual(
            "\nAs a customer, I want this.\n\n"
            "## Acceptance Criteria\n\n1. Works.\n### Detail\nKeep this detail.\n\n"
            "## Context\n\nWhy it matters.\n", requirements(body))

    def test_omits_every_unknown_section_including_qualified_names(self):
        headings = ["Questions", "Feedback", "Analysis", "Challenge", "Created work items",
                    "Pull request", "Test run", "Cause", "Response to the third challenge",
                    "Acceptance Criteria (tightened)", "Original acceptance criteria", "Context extra"]
        body = "## Acceptance Criteria\n1. Plain criteria.\n" + "".join(
            f"\n## {heading}\nOmit.\n### Nested\nAlso omit.\n" for heading in headings)
        self.assertEqual("\n## Acceptance Criteria\n1. Plain criteria.\n", requirements(body))

    def test_matches_case_and_trailing_whitespace_and_keeps_duplicates(self):
        body = ("## CONTEXT  \nFirst.\n\n## acceptance Criteria\t\nCriteria.\n\n"
                "## Context\nSecond.\n")
        self.assertEqual("\n" + body, requirements(body))

    def test_missing_sections_are_not_invented(self):
        for body, expected in [("Preamble only.\n\n", "\nPreamble only.\n"),
                               ("## Analysis\nNotes.\n", ""), ("", ""),
                               ("## Context\nWhy.\n", "\n## Context\nWhy.\n")]:
            with self.subTest(body=body):
                self.assertEqual(expected, requirements(body))

    def test_level_one_heading_ends_a_section_like_other_item_parsers(self):
        self.assertEqual("\n## Context\nKeep.\n\n## Acceptance Criteria\nKeep too.\n",
                         requirements("## Context\nKeep.\n# Notes\nOmit.\n"
                                      "## Acceptance Criteria\nKeep too.\n"))
