"""The original workflow definition's validation of sync steps."""
import unittest

from devteam import workflow


class SyncWorkflow(unittest.TestCase):
    def test_harness_validation(self):
        for action, outcomes, valid in (
            ('sync', ['completed', 'conflicted'], True), ('sync', ['completed'], False),
            ('merged', ['completed', 'conflicted'], False), ('unknown', ['completed'], False)):
            data = {'initial': 'a', 'steps': {'a': {'owner': f'harness:{action}',
                    'transitions': {name: 'a' for name in outcomes}}}}
            if valid:
                workflow.build('test', data, [])
            else:
                with self.assertRaises(workflow.InvalidWorkflow):
                    workflow.build('test', data, [])
