"""Request analysis acceptance checks, using the configured workflow and fake agents."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from textual.widgets import TextArea

from devteam import questions, tui
from devteam.backlog import InvalidRecord, Repository
from devteam.cli import main
from devteam.config import ROOT, load_roles
from devteam.runner import Runner, render
from devteam.workflow import load


class Requests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Repository(Path(self.temp.name) / 'backlog')
        self.request = self.repo.create('request', 'An idea', 'Customer intent.\n')
        self.roles = load_roles()

    def current(self):
        return self.repo.scan().valid[self.request.id]

    def run_reply(self, reply):
        def engine(role, prompt, cwd, extra_dir, log):
            log.write_text('fake transcript')
            return 0, reply
        runner = Runner(self.repo, self.roles, engine, report=lambda message: None)
        runner.run_pass()
        return runner

    def test_capture_defaults_and_parent_rejection(self):
        self.assertEqual(self.repo.root / 'requests/REQUEST-001.md', self.request.path)
        self.assertEqual(('analysis', 'submitted'),
                         (self.request.metadata['workflow'], self.request.metadata['step']))
        epic = self.repo.create('epic', 'Epic')
        story = self.repo.create('story', 'Story', parent=epic.id)
        task = self.repo.create('task', 'Task', parent=story.id)
        bug = self.repo.create('bug', 'Bug')
        for item in (story, task, bug):
            self.assertEqual(('default', 'captured'), (item.metadata['workflow'], item.metadata['step']))
        with self.assertRaisesRegex(InvalidRecord, 'requests must have no parent'):
            self.repo.create('request', 'Bad', parent=epic.id)
        self.assertEqual({}, self.repo.scan().errors)

    def test_cli_capture_list_and_parent_diagnostic(self):
        prefix = ['--product', self.temp.name, 'backlog']
        with contextlib.redirect_stdout(io.StringIO()) as output:
            main(prefix + ['capture', 'request', 'Another idea'])
            main(prefix + ['list'])
        self.assertIn('created REQUEST-002', output.getvalue())
        self.assertRegex(output.getvalue(), r'REQUEST-002\s+submitted\s+human\s+Another idea')
        with self.assertRaises(SystemExit) as raised:
            main(prefix + ['capture', 'request', 'Bad', '--parent', 'EPIC-001'])
        self.assertIn('requests must have no parent', str(raised.exception))
        self.assertNotIn('REQUEST-003', self.repo.scan().valid)

    def test_workflow_roles_prompts_and_hub_transitions(self):
        workflow = load('analysis')
        self.assertEqual('submitted', workflow.initial)
        self.assertEqual({'questions', 'architect', 'platform-engineer', 'quality-lead', 'complete'},
                         set(workflow.steps['product-owner'].transitions))
        for name in ('product-owner', 'architect', 'platform-engineer', 'quality-lead'):
            step = workflow.steps[name]
            self.assertTrue(self.roles[step.role].brief().strip())
            self.assertTrue((ROOT / 'prompts/analysis' / f'{name}.md').is_file())
            if name != 'product-owner':
                self.assertEqual({'questions', 'return'}, set(step.transitions))
        self.repo.transition(self.request.id, 'analyse')
        self.assertEqual('product-owner', self.current().metadata['step'])

    def test_workflow_scoped_prompt_precedence_and_legacy_fallback(self):
        review = load('default').steps['review']
        self.assertTrue(render(review, {}, 'default').startswith((ROOT / 'prompts/review.md').read_text()))
        step = load('analysis').steps['product-owner']
        self.assertTrue(render(step, {}, 'analysis').startswith(
            (ROOT / 'prompts/analysis/product-owner.md').read_text()))
        with tempfile.TemporaryDirectory() as directory, patch('devteam.runner.ROOT', Path(directory)):
            prompts = Path(directory) / 'prompts'
            (prompts / 'analysis').mkdir(parents=True)
            (prompts / 'default').mkdir()
            (prompts / 'review.md').write_text('Fallback review\n')
            (prompts / 'analysis/review.md').write_text('Analysis review\n')
            self.assertTrue(render(review, {}, 'analysis').startswith('Analysis review\n'))
            self.assertTrue(render(review, {}, 'default').startswith('Fallback review\n'))
            (prompts / 'default/review.md').write_text('Default review\n')
            self.assertTrue(render(review, {}, 'default').startswith('Default review\n'))

    def test_specialists_cannot_complete_and_runner_uses_request_prompt(self):
        for name in ('architect', 'platform-engineer', 'quality-lead'):
            with self.subTest(role=name):
                request = self.current()
                request.metadata['step'] = name
                request.path.write_text(request.render())
                before = request.path.read_bytes()
                runner = self.run_reply('TRANSITION: complete')
                self.assertIn('not a transition', runner.failed[request.id])
                self.assertEqual(before, request.path.read_bytes())
                self.run_reply('TRANSITION: return')
                self.assertEqual('product-owner', self.current().metadata['step'])

    def test_runner_disambiguates_agent_steps_with_the_same_name(self):
        root = Path(self.temp.name)
        workflows = root / 'workflows'
        workflows.mkdir()
        for name in ('default', 'analysis'):
            definition = json.loads((ROOT / 'workflows' / f'{name}.json').read_text())
            if name == 'analysis':
                # A future agent-owned step may share a name with default's analysis.
                definition['initial'] = 'analysis'
                definition['steps']['analysis'] = {
                    'owner': 'agent:product_owner', 'transitions': {'complete': 'review'},
                }
            (workflows / f'{name}.json').write_text(json.dumps(definition))
        repo = Repository(root / 'mixed-backlog', workflows)
        request = repo.create('request', 'Idea')
        epic = repo.create('epic', 'Epic')
        story = repo.create('story', 'Story', parent=epic.id)
        repo.transition(story.id, 'analyse')
        prompts = root / 'prompts'
        (prompts / 'analysis').mkdir(parents=True)
        (prompts / 'analysis.md').write_text('Default analysis prompt\n')
        (prompts / 'analysis/analysis.md').write_text('Request analysis prompt\n')
        calls = []

        def engine(role, prompt, cwd, extra_dir, log):
            calls.append(role.name)
            expected, transition = {
                'product_owner': ('Request analysis prompt\n', 'complete'),
                'analyst': ('Default analysis prompt\n', 'analysed'),
                'challenger': ('', 'sound'),
            }[role.name]
            self.assertTrue(prompt.startswith(expected))
            log.write_text('fake transcript')
            return 0, f'TRANSITION: {transition}'

        with patch('devteam.runner.ROOT', root):
            runner = Runner(repo, self.roles, engine, report=lambda message: None)
            runner.run(once=True)
        self.assertEqual({}, runner.failed)
        self.assertCountEqual(['product_owner', 'analyst', 'challenger'], calls)
        self.assertEqual('review', repo.scan().valid[request.id].metadata['step'])
        self.assertEqual('ready', repo.scan().valid[story.id].metadata['step'])

    def test_every_roles_questions_preserve_answers_and_return_to_same_role(self):
        for number, name in enumerate(('product-owner', 'architect', 'platform-engineer', 'quality-lead')):
            with self.subTest(role=name):
                request = self.current()
                request.metadata['step'] = name
                request.path.write_text(request.render())
                previous = request.body

                def engine(role, prompt, cwd, extra_dir, log):
                    self.assertTrue(prompt.startswith((ROOT / f'prompts/analysis/{name}.md').read_text()))
                    body = previous + ('\n## Questions\n\n' if number == 0 else '')
                    self.repo.write_body(request.id, body + f'{number + 1}. Question from {name}?\n', 'questions')
                    log.write_text('fake transcript')
                    return 0, 'TRANSITION: questions'

                Runner(self.repo, self.roles, engine, report=lambda message: None).run_pass()
                self.assertEqual(name + '-questions', self.current().metadata['step'])
                body = questions.answer(self.current().body, {number: f'Answer for {name}.'})
                self.repo.write_body(request.id, body, 'answers')
                self.repo.transition(request.id, 'answered')
                self.assertEqual(name, self.current().metadata['step'])
                self.assertIn(previous, self.current().body)
                self.assertTrue(all(question.answered for question in questions.parse(self.current().body)))

    def test_complete_review_and_mixed_workflows(self):
        self.repo.transition(self.request.id, 'analyse')
        created = []

        def engine(role, prompt, cwd, extra_dir, log):
            self.assertEqual('product_owner', role.name)
            self.assertIn('Before choosing `complete`', prompt)
            epic = self.repo.create('epic', 'Intent')
            story = self.repo.create('story', 'For the audience', '## Acceptance criteria\n\n- Reflect answers.\n', parent=epic.id)
            task = self.repo.create('task', 'Support feature', parent=story.id)
            bug = self.repo.create('bug', 'Fix existing behaviour', parent=story.id)
            created.extend([epic, story, task, bug])
            self.repo.write_body(self.request.id, self.current().body + '\n## Created work items\n\n' +
                                 '\n'.join(f'- {item.id}: {item.metadata["title"]}' for item in created) + '\n', 'items')
            log.write_text('fake transcript')
            return 0, 'TRANSITION: complete'

        runner = Runner(self.repo, self.roles, engine, report=lambda message: None)
        runner.run(once=True)
        self.assertEqual('review', self.current().metadata['step'])
        self.assertEqual({}, self.repo.scan().errors)
        for item in created:
            self.assertIn(item.id, self.current().body)
        self.assertEqual([], runner.pending())
        self.repo.transition(self.request.id, 'revise')
        self.assertEqual('product-owner', self.current().metadata['step'])
        self.repo.transition(self.request.id, 'complete')
        self.repo.transition(self.request.id, 'approve')
        self.assertEqual('done', self.current().metadata['step'])
        for item in created[1:]:
            fresh = self.repo.scan().valid[item.id]
            self.assertEqual(self.repo.workflow(fresh.metadata['workflow']).initial, fresh.metadata['step'])
        story = created[1]
        for transition in ('analyse', 'analysed', 'sound', 'play', 'implemented', 'written', 'passed'):
            self.repo.transition(story.id, transition)
        # The same step name has different ownership in the two workflows.
        request = self.current()
        request.metadata['step'] = 'review'
        request.path.write_text(request.render())
        rows = {row.key: row for row in tui.rows(self.repo)}
        self.assertEqual(('review', 'YOU'), (rows[request.id].step, rows[request.id].waiting_on))
        self.assertEqual(('review', 'reviewer'), (rows[story.id].step, rows[story.id].waiting_on))
        self.assertEqual([story.id], [record.id for record, step in runner.pending()])


class NewRequestUI(unittest.IsolatedAsyncioTestCase):
    async def test_new_request_preserves_text_and_derives_title(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / 'backlog')
            app = tui.Backlog(repo)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press('n')
                await pilot.pause()
                self.assertIsInstance(app.screen, tui.NewRequest)
                await pilot.press('ctrl+s')
                self.assertIsInstance(app.screen, tui.NewRequest)
                self.assertEqual({}, repo.scan().valid)
                text = 'A' * 100 + '\nFull customer text with café.\n'
                app.screen.query_one(TextArea).text = text
                await pilot.press('ctrl+s')
                await pilot.pause()
                request = repo.scan().valid['REQUEST-001']
                self.assertEqual(text, request.body)
                self.assertEqual('A' * 80, request.metadata['title'])
                self.assertEqual('submitted', request.metadata['step'])
                self.assertIn('REQUEST-001', [row.key for row in app.data])
                await pilot.press('n', 'escape')
                await pilot.pause()
                self.assertEqual(1, len(repo.scan().valid))
