import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from devteam import engines, render
from devteam.backlog import Repository
from devteam.config import Role, load_roles
from devteam.runner import Runner
from tests.test_runner import WORKFLOW


# Recorded stream-json event shapes; UUID/session/usage fields are immaterial here.
ASSISTANT = '{"type":"assistant","message":{"content":[{"type":"text","text":"Done.\\n"},{"type":"tool_use","name":"Read","input":{"file_path":"README.md"}}]}}\n'
RESULT = '{"type":"result","subtype":"success","result":"Done.\\nTRANSITION: ready"}\n'
SUCCESS = '{"type":"system","subtype":"init"}\n' + ASSISTANT + '{"type":"user","message":{"content":[{"type":"tool_result","content":"noise"}]}}\n' + RESULT


class Streams(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / 'run.log'

    def invoke(self, stdout, stderr='', code=0, stream='claude-json', on_line=None):
        (self.root / 'stdout').write_text(stdout)
        (self.root / 'stderr').write_text(stderr)
        script = self.root / 'agent.py'
        script.write_text('import pathlib, sys\nsys.stdout.write(pathlib.Path("stdout").read_text())\n'
                          'sys.stdout.flush()\nsys.stderr.write(pathlib.Path("stderr").read_text())\n'
                          f'sys.exit({code})\n')
        role = Role('analyst', 'arbitrary-name', 'm', 5, [sys.executable, str(script)], 'w', stream=stream)
        return engines.run(role, '', self.root, self.root, self.log, on_line=on_line)

    def test_recorded_stream_replies_and_raw_log(self):
        for stdout, code, expected in (
            (SUCCESS, 0, (0, 'Done.\nTRANSITION: ready')),
            (ASSISTANT, 0, (0, 'Done.\n')),
            ('malformed\n' + SUCCESS, 0, (0, 'Done.\nTRANSITION: ready')),
            (SUCCESS, 7, (7, 'Done.\nTRANSITION: ready')),
            ('{"type":"system"}\n', 0, (1, '')),
            ('malformed\n', 7, (7, '')),
            (RESULT + '{"type":"result","result":"last"}\n', 0, (0, 'last')),
            ('{"type":"result","result":""}\n', 0, (0, '')),
        ):
            with self.subTest(stdout=stdout, code=code):
                self.assertEqual(expected, self.invoke(stdout, code=code))
                self.assertEqual(stdout, self.log.read_text().split('\n\n', 1)[1])

    def test_text_and_unknown_stream_keep_stdout_only(self):
        for stream in ('text', 'unknown'):
            received = []
            self.assertEqual((4, 'reply\n'), self.invoke('reply\n', 'progress\n', 4, stream, received.append))
            self.assertCountEqual(['reply', 'progress'], received)
            self.assertCountEqual(['reply', 'progress'], self.log.read_text().split('\n\n', 1)[1].splitlines())

    def test_display_failures_do_not_change_reply(self):
        def broken(line):
            raise ValueError('listener failed')
        self.assertEqual((0, 'Done.\nTRANSITION: ready'), self.invoke(SUCCESS, on_line=broken))
        with patch.dict(render.STREAMS, {'claude-json': (broken, render.claude_reply)}):
            self.assertEqual((0, 'Done.\nTRANSITION: ready'), self.invoke(SUCCESS, on_line=lambda line: None))

    def test_both_pipes_reach_log_and_listener_before_exit(self):
        script = self.root / 'agent.py'
        script.write_text('''import pathlib, sys, time
for name, pipe in (("stdout", sys.stdout), ("stderr", sys.stderr)):
    print(name, file=pipe, flush=True)
    deadline = time.monotonic() + 5
    while not pathlib.Path(name + ".ack").exists():
        if time.monotonic() > deadline:
            sys.exit(9)
        time.sleep(.01)
pathlib.Path("exited").touch()
''')
        received = []
        observations = []

        def listener(line):
            received.append(line)
            observations.append((not (self.root / 'exited').exists(), line + '\n' in self.log.read_text()))
            (self.root / (line + '.ack')).touch()

        role = Role('analyst', 'fake', 'm', 5, [sys.executable, str(script)], 'w')
        self.assertEqual((0, 'stdout\n'), engines.run(role, '', self.root, self.root, self.log, on_line=listener))
        self.assertEqual(['stdout', 'stderr'], received)
        self.assertEqual([(True, True), (True, True)], observations)
        self.assertEqual('stdout\nstderr\n', self.log.read_text().split('\n\n', 1)[1])

    def test_runner_passes_registered_listener(self):
        workflows = self.root / 'workflows'
        workflows.mkdir()
        (workflows / 'default.json').write_text(json.dumps(WORKFLOW))
        roles = load_roles()
        repo = Repository(self.root / 'backlog', workflows, roles)
        epic = repo.create('epic', 'Epic')
        story = repo.create('story', 'Story', parent=epic.id)
        repo.transition(story.id, 'analyse')
        received = []

        def engine(role, prompt, cwd, extra_dir, log, *, on_line):
            on_line('live')
            return 0, 'TRANSITION: ready'

        runner = Runner(repo, roles, engine, report=lambda message: None)
        runner.on_line = received.append
        runner.run(once=True)
        self.assertEqual(['live'], received)
        self.assertEqual('ready', repo.scan().valid[story.id].metadata['step'])


class Rendering(unittest.TestCase):
    def test_event_shapes_and_truncation(self):
        self.assertEqual('Done.\ntool: Read README.md', render.claude_json(ASSISTANT))
        for line in ('null', '[]', '1', '"text"', '{}', '{"type":"system"}',
                     '{"type":"user"}', '{"type":"assistant","message":null}',
                     '{"type":"assistant","message":{"content":[null,{}, {"type":"text","text":5}]}}'):
            with self.subTest(line=line):
                self.assertIsNone(render.claude_json(line))
        self.assertEqual('bad json', render.claude_json('bad json\n'))
        self.assertEqual('x' * 197 + '...', render.claude_json('x' * 201))
        for args, expected in (({'path': 'p', 'command': 'c'}, 'p'),
                               ({'file_path': 'f', 'path': 'p'}, 'f'), ({}, ''), (None, '')):
            line = json.dumps({'type': 'assistant', 'message': {'content': [
                {'type': 'tool_use', 'name': 'Tool', 'input': args}]}})
            self.assertEqual(('tool: Tool ' + expected).rstrip(), render.claude_json(line))
        line = json.dumps({'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'x' * 300}]}})
        self.assertEqual('x' * 197 + '...', render.claude_json(line))

    def test_reply_ignores_wrong_types(self):
        stream = '\n'.join(('[]', 'invalid', '{"type":"result","result":42}',
                             '{"type":"assistant","message":{"content":"bad"}}'))
        self.assertEqual((1, ''), render.claude_reply(0, stream))
