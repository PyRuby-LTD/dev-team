from pathlib import Path
import re
import unittest

from devteam import questions

FIXTURES = Path(__file__).parent / 'fixtures' / 'questions'
ROUND_TWO = '## Questions\n\n1. First?\n\n   **Answer:** yes\n' + ''.join(
    f'\n{i}. Next?\n\n   **Answer:**\n' for i in range(2, 6))


class Parsing(unittest.TestCase):
    def flags(self, body):
        return [q.answered for q in questions.parse(body)]

    def test_round_two_placeholders(self):
        self.assertEqual([True, False, False, False, False], self.flags(ROUND_TWO))
        for marker in ('**Answer:**', '**Answer:** ', '> **Answer:**', 'Answer:'):
            for note in ('', '   Note: see below', '   - option', '    text', 'text'):
                with self.subTest(marker=marker, note=note):
                    self.assertEqual([False], self.flags(f'## Questions\n1. A?\n   {marker}\n{note}\n'))

    def test_answer_fills_placeholder_and_preserves_note(self):
        body = ROUND_TWO.replace('3. Next?\n\n   **Answer:**',
                                 '3. Next?\n\n   **Answer:**\n   Note: see below')
        body = questions.answer(body, {2: 'Friday.\nNo later.'})
        self.assertIn('3. Next?\n\n   **Answer:** Friday.\n   No later.\n   Note: see below', body)
        self.assertEqual(5, body.count('**Answer:**'))
        self.assertEqual([True, False, True, False, False], self.flags(body))
        body = questions.answer(body, {1: 'yes', 3: 'yes', 4: 'yes'})
        self.assertEqual([True] * 5, self.flags(body))
        self.assertEqual(5, body.count('**Answer:**'))

    def test_three_rounds_with_lists_in_answers(self):
        body = '## Questions\n1. First?\n'
        for count, addition in ((1, ''), (2, '2. Second?\n   **Answer:**\n'), (3, '3. Third?\n')):
            body += addition
            self.assertEqual([True] * (count - 1) + [False], self.flags(body))
            body = questions.answer(body, {count - 1: 'yes\n- item\n1. item'})
            self.assertEqual([True] * count, self.flags(body))

    def test_nested_answer_lists_and_question_options(self):
        for indent in (3, 4):
            with self.subTest(indent=indent):
                body = '## Questions\n1. A?\n   **Answer:** yes\n' + ' ' * indent + '- item\n' + ' ' * indent + '1. item\n'
                self.assertEqual([True], self.flags(body))
        body = '## Questions\n1. A?\n   - option a\n   - option b\n2. B?\n- Any budget?\n'
        found = questions.parse(body)
        self.assertEqual([False] * 3, self.flags(body))
        self.assertEqual('A? - option a - option b', found[0].text)
        for gap in ('', '\n'):
            self.assertEqual([True, False], self.flags('## Questions\n1. A?\n   **Answer:** yes\n' + gap + '2. B?\n'))

    def test_base_indent_resets_at_repeated_heading(self):
        body = '## Questions\n   1. A?\n    - nested\n  2. B?\n## Questions\n1. C?\n   - nested\n'
        self.assertEqual([False] * 3, self.flags(body))

    def test_exact_heading_rule_and_settled_questions(self):
        self.assertEqual([False, False], self.flags('## Questions\n1. A?\n### Questions\n2. B?\n'))
        for heading in ('## Questions (round 2)', '### Questions already settled'):
            with self.subTest(heading=heading):
                self.assertEqual([], self.flags(f'## Findings\n{heading}\n1. A?\n'))
                self.assertEqual([True], self.flags('## Questions\n1. A?\n   **Answer:** yes\n' + heading + '\n2. B?\n'))

    def test_placeholder_preserves_line_endings_and_final_newline(self):
        for newline in ('\n', '\r\n'):
            for trailing in ('', newline):
                with self.subTest(newline=newline, trailing=trailing):
                    body = newline.join(['## Questions', '1. A?', '   **Answer:**']) + trailing
                    expected = newline.join(['## Questions', '1. A?', '   **Answer:** yes', '   - item']) + trailing
                    self.assertEqual(expected, questions.answer(body, {0: 'yes\n- item'}))

    def test_answer_requires_colon_and_inline_text(self):
        self.assertEqual([False], self.flags('## Questions\n1. A?\nAnswer options are:\n'))
        for marker in ('**Answer:** x', '> **Answer:** x', 'Answer: x', '**Answer**: x'):
            with self.subTest(marker=marker):
                self.assertEqual([True], self.flags(f'## Questions\n1. A?\n{marker}\n'))

    def test_real_bodies(self):
        # Counts read by hand from the working-tree Questions sections before copying.
        expected = {'REQUEST-001': [True], 'REQUEST-002': [True],
                    'STORY-006': [True] * 6, 'STORY-009': [True] * 4,
                    'STORY-010': [True] * 2, 'STORY-011': [True], 'STORY-012': [True] * 4}
        for ident, flags in expected.items():
            with self.subTest(ident=ident):
                self.assertEqual(flags, self.flags((FIXTURES / f'{ident}.md').read_text()))
        story = (FIXTURES / 'STORY-012.md').read_text()
        self.assertIn('   **Answer:** See gh_api_10_<call>.txt files in the root\n2.', story)
        self.assertIn('\nQuestions 1 and 2 are answered', story)
        self.assertIn('Questions 1 and 2 are answered', questions.parse(story)[-1].text)
        self.assertEqual([True, False, False, False, False],
                         self.flags((FIXTURES / 'STORY-006-round-two.md').read_text()))

    def test_analysis_prompts_discourage_placeholders(self):
        sentence = "Do not write an `**Answer:**` line under a new question; the customer's reply is added beneath it. Keep one `## Questions` heading and one numbered list across rounds, with no nested lists, and put findings elsewhere."
        root = Path(__file__).resolve().parents[1]
        paths = [root / 'prompts/analysis.md', *sorted((root / 'prompts/analysis').glob('*.md'))]
        self.assertEqual(5, len(paths))
        for path in paths:
            with self.subTest(path=path):
                self.assertIn(sentence, re.sub(r'\s+', ' ', path.read_text()))
