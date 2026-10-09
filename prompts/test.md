Add integration tests for this work item to the regression suite in the
repository at {{checkout}}. You are on branch {{branch}}. Leave your changes in
the working tree: the runner commits them to that branch when you finish, so do
not run `git commit` yourself. Change tests, fixtures, canned data, stubs and
the Makefile's test target only, not the code under test.

Add or extend a small number of narrative tests that exercise the running
system and cover the story's main journeys. Leave criteria better proven by
unit tests to the implementer's unit tests.
Run a single test with `{{harness_command}} check <test>`
and the whole suite with `{{harness_command}} check`.

Read the latest workflow check log: {{verify_log}}. If it shows a failure,
work out whether the tests or the code are wrong.

Record under a `## Tests` heading in the item body, replacing any earlier one,
which narrative tests cover the story's main journeys, which criteria are left
to unit tests, and how to run one test on its own.

Choose `written` when the narrative tests cover the story's main journeys,
every criterion is either covered by one of them or recorded as left to unit
tests, and the whole suite passes for you; the harness then runs it again.
Choose `defect` when a test shows the code
does not meet a criterion or breaks existing behaviour: name the failing test,
what it expected and the relative path of the failing run's log, and leave
the test in place. The implementer's latest workflow check log predates this
run, so give the path printed by `dev-team check`.
