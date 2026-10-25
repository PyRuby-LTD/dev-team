"""Dependency validation, isolated edits and scheduling with real backlogs and Git."""
import contextlib
import io
import unittest

import yaml

from devteam import git
from devteam.backlog import InvalidRecord, Repository, parse
from devteam.cli import main
from devteam.runner import Runner
from tests import test_backlog, test_backlog_writes, test_checkout, test_runner, test_merged


class DependencyValidation(unittest.TestCase):
    setUp = test_backlog.BacklogAcceptance.setUp

    def put(self, record, **changes):
        data = dict(record.metadata, **changes)
        record.path.write_text('---\n' + yaml.safe_dump(data, sort_keys=False) + '---\n' + record.body)

    def test_valid_ids_roundtrip_for_stories_tasks_and_bugs(self):
        dependency = self.repo.create('bug', 'Dependency')
        for record in (self.story, self.repo.create('task', 'Task', parent=self.story.id),
                       self.repo.create('bug', 'Bug')):
            self.repo.set_dependencies(record.id, [dependency.id])
            reopened = self.repo.scan().valid[record.id]
            self.assertEqual([dependency.id], reopened.metadata['depends_on'])
            self.assertEqual(reopened.metadata, parse(record.path, reopened.render()).metadata)

    def test_invalid_values_report_per_file_without_writing_or_affecting_unrelated_work(self):
        dependency = self.repo.create('bug', 'Dependency')
        request = self.repo.create('request', 'Request')
        cases = [
            (['STORY-missing'], 'STORY-missing'),
            ([self.story.id], self.story.id),
            ([123], '123'), ([None], 'None'), (['bad'], 'bad'),
            ([dependency.id, dependency.id], f'repeats {dependency.id}'),
            ('BUG-001', 'must be a list'), (None, 'must be a list'),
            ([self.epic.id], 'epic never reaches done'),
            ([request.id], "request's done does not mean merged work"),
        ]
        for value, message in cases:
            with self.subTest(value=value):
                self.put(self.story, depends_on=value)
                before = {p: p.read_bytes() for p in self.root.rglob('*.md')}
                snapshot = self.repo.scan()
                self.assertIn(message, str(snapshot.errors[self.story.path]))
                self.assertEqual({self.epic.id, dependency.id, request.id}, set(snapshot.valid))
                self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.put(self.story)
        for record in (self.epic, request):
            self.put(record, depends_on=[])
            self.assertIn('must have no depends_on', str(self.repo.scan().errors[record.path]))
            self.put(record)

    def test_dependency_cycles_name_chain_and_quarantine_children(self):
        second = self.repo.create('bug', 'Second')
        third = self.repo.create('bug', 'Third')
        child = self.repo.create('task', 'Child', parent=self.story.id)
        for record, dependency in ((self.story, second), (second, third), (third, self.story)):
            self.put(record, depends_on=[dependency.id])
        snapshot = self.repo.scan()
        for record in (self.story, second, third):
            errors = str(snapshot.errors[record.path])
            self.assertIn('dependency cycle:', errors)
            for item in (self.story, second, third):
                self.assertIn(item.id, errors)
        self.assertIn(f'parent {self.story.id} has validation errors', str(snapshot.errors[child.path]))
        self.assertEqual({self.epic.id}, set(snapshot.valid))

    def test_bad_dependency_propagates_across_links_and_parent_links(self):
        bad = self.repo.create('bug', 'Bad')
        intermediate = self.repo.create('bug', 'Intermediate', depends_on=[bad.id])
        self.repo.set_dependencies(self.story.id, [intermediate.id])
        child = self.repo.create('task', 'Child', parent=self.story.id)
        for changes in ({'parent': 'EPIC-missing'}, {'title': None}):
            with self.subTest(changes=changes):
                self.put(bad, **changes)
                snapshot = self.repo.scan()
                self.assertIn(bad.id, str(snapshot.errors[intermediate.path]))
                self.assertIn(intermediate.id, str(snapshot.errors[self.story.path]))
                self.assertIn(self.story.id, str(snapshot.errors[child.path]))
                self.assertEqual({self.epic.id}, set(snapshot.valid))


class DependencyWrites(unittest.TestCase):
    setUp = test_backlog_writes.BacklogWrites.setUp

    def command(self, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            main(['--product', str(self.top), 'backlog', *args])

    def test_cli_capture_and_replace_commit_only_item_and_reject_without_writing(self):
        self.command('capture', 'story', 'Third', '--parent', self.epic.id,
                     '--depends-on', self.story.id, '--depends-on', self.other.id)
        third = self.repo.scan().valid['STORY-003']
        self.assertEqual([self.story.id, self.other.id], third.metadata['depends_on'])
        self.assertEqual('STORY-003: captured at captured', git.must(self.root, 'log', '-1', '--format=%s'))
        before = third.path.read_bytes()
        self.command('depends-on', third.id, self.other.id)
        self.assertEqual(before.replace(b'depends_on:\n- STORY-001\n- STORY-002\n', b'depends_on: [STORY-002]\n'), third.path.read_bytes())
        self.assertEqual('stories/STORY-003.md', git.must(self.root, 'show', '--format=', '--name-only'))
        self.assertEqual('STORY-003: set depends_on', git.must(self.root, 'log', '-1', '--format=%s'))
        for args in [('depends-on', third.id, 'BUG-missing'),
                     ('capture', 'bug', 'Invalid', '--depends-on', 'BUG-missing')]:
            with self.subTest(args=args):
                files = {p: p.read_bytes() for p in self.root.rglob('*.md')}
                tip = git.must(self.root, 'rev-parse', 'HEAD')
                with self.assertRaisesRegex(SystemExit, 'BUG-missing'):
                    self.command(*args)
                self.assertEqual(files, {p: p.read_bytes() for p in self.root.rglob('*.md')})
                self.assertEqual(tip, git.must(self.root, 'rev-parse', 'HEAD'))
        self.command('depends-on', third.id)
        self.assertEqual([], self.repo.scan().valid[third.id].metadata['depends_on'])

    def test_value_rewrite_preserves_other_front_matter_and_body_and_move_only_changes_step(self):
        original = self.story.path.read_text().replace('title: First', "title: 'First' # comment")
        for field in ('depends_on: [] # keep\n', 'depends_on: [STORY-002]\n',
                      'depends_on:\n- STORY-002\n', ''):
            with self.subTest(field=field):
                text = original.replace('workflow: default\n', field + 'workflow: default\n')
                self.story.path.write_bytes(text.replace('\n', '\r\n').encode())
                self.repo.set_dependencies(self.story.id, [self.other.id])
                updated = self.story.path.read_bytes()
                expected = text.replace(field, 'depends_on: [STORY-002]' + (' # keep' if '# keep' in field else '') + '\n', 1) if field else text.replace('step: captured\n', 'step: captured\ndepends_on: [STORY-002]\n')
                self.assertEqual(expected.replace('\n', '\r\n').encode(), updated)
                self.repo.transition(self.story.id, 'analyse')
                self.assertEqual(updated.replace(b'step: captured', b'step: analysis'), self.story.path.read_bytes())

    def test_command_repairs_invalid_link_and_rejects_cycle_before_writing(self):
        self.repo.set_dependencies(self.story.id, [self.other.id])
        before = self.other.path.read_bytes()
        with self.assertRaisesRegex(InvalidRecord, 'dependency cycle'):
            self.repo.set_dependencies(self.other.id, [self.story.id])
        self.assertEqual(before, self.other.path.read_bytes())
        self.story.path.write_text(self.story.path.read_text().replace('[STORY-002]', '[BUG-missing]'))
        self.repo.set_dependencies(self.story.id, [])
        self.assertIn(self.story.id, self.repo.scan().valid)


class DependencyScheduling(unittest.TestCase):
    setUp = test_checkout.CheckoutAcceptance.setUp
    engine = test_checkout.CheckoutAcceptance.engine
    steps = test_checkout.CheckoutAcceptance.steps

    def test_wait_lists_every_unfinished_dependency_without_claiming_checkout(self):
        third = self.repo.create('bug', 'Third')
        self.repo.set_dependencies(self.first.id, [self.second.id, third.id])
        self.repo.transition(self.first.id, 'play')
        record = self.repo.scan().valid[self.first.id]
        self.assertFalse(self.runner.claim(record, self.repo.step(record)))
        self.assertIsNone(self.runner.checkout_user)
        self.assertEqual(f'waiting for {self.second.id} (ready), {third.id} (ready) to be done', self.runner.waiting[self.first.id])
        self.assertFalse(git.has_ref(self.product, f'refs/heads/devteam/{self.first.id}'))
        self.repo.transition(self.second.id, 'play')
        self.runner.run(once=True)
        self.assertEqual('accept', self.steps()[self.second.id])
        self.assertTrue(all(call[0] == self.second.id for call in self.calls))
        self.assertNotIn(self.first.id, self.runner.failed)

    def test_hold_lifts_only_after_last_dependency_is_done_on_same_runner(self):
        third = self.repo.create('bug', 'Third')
        self.repo.set_dependencies(self.first.id, [self.second.id, third.id])
        self.repo.transition(self.first.id, 'play')
        for dependency in (self.second, third):
            self.runner.run(once=True)
            self.assertEqual('implement', self.steps()[self.first.id])
            self.assertEqual([], self.calls)
            dependency.path.write_text(dependency.path.read_text().replace('step: ready', 'step: done'))
        self.runner.run(once=True)
        self.assertEqual('accept', self.steps()[self.first.id])
        self.assertNotIn(self.first.id, self.runner.waiting)
        self.assertEqual('main', git.base_of(self.product, f'devteam/{self.first.id}'))

    def test_existing_branch_bypasses_hold_even_with_abandoned_dependency(self):
        # Add the terminal state to the custom workflow fixture.
        definition = self.repo.workflow('default')
        from devteam.workflow import Step
        definition.steps['abandoned'] = Step('abandoned', 'human', {})
        self.second.path.write_text(self.second.path.read_text().replace('step: ready', 'step: abandoned'))
        self.repo.set_dependencies(self.first.id, [self.second.id])
        git.must(self.product, 'branch', f'devteam/{self.first.id}')
        git.must(self.product, 'config', f'branch.devteam/{self.first.id}.base', 'main')
        self.repo.transition(self.first.id, 'play')
        self.runner.run(once=True)
        self.assertEqual('accept', self.steps()[self.first.id])
        self.assertNotIn(self.first.id, self.runner.waiting)

    def test_analysis_runs_with_unfinished_dependencies(self):
        self.repo.set_dependencies(self.first.id, [self.second.id])
        self.repo.transition(self.first.id, 'analyse')
        self.runner.run(once=True)
        self.assertEqual('ready', self.steps()[self.first.id])
        self.assertEqual(['analyst'], [call[1] for call in self.calls])
        self.assertEqual('main', git.current_branch(self.product))


class DependencyMerge(unittest.TestCase):
    setUp = test_merged.Merged.setUp
    no_engine = test_merged.Merged.no_engine
    advance = test_merged.Merged.advance

    def test_next_scan_starts_from_merged_base_without_restart(self):
        self.repo.set_dependencies(self.other.id, [self.item.id])
        self.other.path.write_text(self.other.path.read_text().replace('step: captured', 'step: implement'))
        other = self.repo.scan().valid[self.other.id]
        self.assertFalse(self.runner.claim(other, self.repo.step(other)))
        tip = self.advance(self.writer, 'merged-work')
        git.must(self.writer, 'push', '-q', 'origin', 'main')
        self.assertEqual(1, self.runner.run_pass())
        self.assertEqual('done', self.repo.scan().valid[self.item.id].metadata['step'])
        other = self.repo.scan().valid[self.other.id]
        self.assertTrue(self.runner.claim(other, self.repo.step(other)))
        self.runner.take_checkout(other)
        self.assertEqual('main', git.base_of(self.product, f'devteam/{other.id}'))
        self.assertEqual(tip, git.must(self.product, 'rev-parse', 'HEAD'))
        self.assertTrue((self.product / 'merged-work.txt').exists())

    def test_abandoned_blocks_until_customer_removes_dependency(self):
        self.item.path.write_text(self.item.path.read_text().replace('step: merged', 'step: accept'))
        self.repo.transition(self.item.id, 'abandon')
        self.assertEqual(1, self.runner.run_pass())
        self.assertEqual('abandoned', self.repo.scan().valid[self.item.id].metadata['step'])
        self.assertEqual('main', git.current_branch(self.product))
        self.repo.set_dependencies(self.other.id, [self.item.id])
        self.other.path.write_text(self.other.path.read_text().replace('step: captured', 'step: implement'))
        other = self.repo.scan().valid[self.other.id]
        self.assertFalse(self.runner.claim(other, self.repo.step(other)))
        reason = self.runner.waiting[other.id]
        self.assertIn(f'blocked by abandoned {self.item.id}', reason)
        self.assertIn('customer must edit depends_on', reason)
        self.assertIsNone(self.runner.checkout_user)
        self.repo.set_dependencies(other.id, [])
        other = self.repo.scan().valid[other.id]
        self.assertTrue(self.runner.claim(other, self.repo.step(other)))

    def test_checks_and_harness_actions_are_exempt(self):
        dependency = self.repo.create('bug', 'Unfinished')
        self.repo.set_dependencies(self.item.id, [dependency.id])
        record = self.repo.scan().valid[self.item.id]
        for name in ('merged', 'verify'):
            with self.subTest(step=name):
                step = self.repo.workflow('default').steps[name]
                self.assertIsNone(self.runner.dependency_wait(record, step, self.repo.scan()))


class DependencyAgentEdits(unittest.TestCase):
    setUp = test_runner.RunnerAcceptance.setUp
    runner = test_runner.RunnerAcceptance.runner
    step = test_runner.RunnerAcceptance.step

    def test_valid_dependency_edits_by_hand_or_command_are_accepted(self):
        for by_hand in (False, True):
            with self.subTest(by_hand=by_hand):
                self.story.path.write_text(self.story.render().replace('step: captured', 'step: analysis'))
                def edit(prompt):
                    if by_hand:
                        text = self.story.path.read_text().replace('step: analysis', 'step: analysis\ndepends_on: [STORY-002]')
                        self.story.path.write_text(text)
                    else:
                        self.repo.set_dependencies(self.story.id, [self.other.id])
                    return 0, 'TRANSITION: ready'
                runner = self.runner({self.story.id: [edit]})
                runner.run(once=True)
                self.assertEqual({}, runner.failed)
                self.assertEqual('ready', self.step(self.story))

    def test_invalid_dependencies_or_other_metadata_changes_still_fail_guard(self):
        cases = ('[BUG-missing]', '[STORY-001]', 'not-a-list', '[STORY-002, STORY-002]')
        for value in (*cases, '[STORY-002]'):
            with self.subTest(value=value):
                self.story.path.write_text(self.story.render().replace('step: captured', 'step: analysis'))
                def edit(prompt):
                    text = self.story.path.read_text().replace('step: analysis', f'step: analysis\ndepends_on: {value}')
                    if value == '[STORY-002]':
                        text = text.replace('title: First', 'title: Changed')
                    self.story.path.write_text(text)
                    return 0, 'TRANSITION: ready'
                runner = self.runner({self.story.id: [edit]})
                runner.run(once=True)
                self.assertIn("the agent changed or broke the item's front matter", runner.failed[self.story.id])
