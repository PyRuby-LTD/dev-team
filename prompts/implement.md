Implement this work item in the repository at {{checkout}}. You are on branch
{{branch}}. Leave your changes in the working tree: the runner commits them to
that branch when you finish, so do not run `git commit` yourself.

Work against the acceptance criteria in the item. If the item has a `## Review`
section, address its findings; if its `## Tests` section reports a defect, fix
the code rather than the test. Run your unit tests directly; the full suite is
run for you after the tester's step.

If `## Pull request feedback` is present, address every comment there. It holds
the whole history of the PR with dates; comments the code already meets need no
further change. The latest `## Feedback` note takes precedence.

Read the latest workflow check log: {{verify_log}}.

Record what you changed and the checks and their results under an
`## Implementation` heading in the item body, replacing any earlier one.
For each acceptance criterion, record whether it is covered by a unit test,
left to the tester's narrative tests, or has no test and why. Write the reason
as a note under that heading so the tester and reviewer can challenge the
decision or add their own test.

Choose `implemented` when you have changed the code to meet the criteria and
findings you could meet. Choose `blocked` when you cannot make progress without
the customer, or when what remains is something you cannot do from here, such
as a criterion needing access you do not have. Say under `## Implementation`
exactly what is blocked, what you tried and what you need; the item then goes
back to the customer.
