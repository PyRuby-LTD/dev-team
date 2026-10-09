Add integration tests for this work item to the regression suite in the
repository at {{checkout}}. You are on branch {{branch}}. Leave your changes in
the working tree: the runner commits them to that branch when you finish, so do
not run `git commit` yourself. Change tests, fixtures, canned data, stubs and
the Makefile's test target only, not the code under test.

Give each acceptance criterion in the item at least one test that exercises the
running system. Run a single test with `{{harness_command}} check <test>`
and the whole suite with `{{harness_command}} check`.

Read the latest workflow check log: {{verify_log}}. If it shows a failure,
work out whether the tests or the code are wrong.

Record under a `## Tests` heading in the item body, replacing any earlier one,
which test covers each criterion and how to run one test on its own.

Choose `written` when every criterion is covered and the whole suite passes for
you; the harness then runs it again. Choose `defect` when a test shows the code
does not meet a criterion or breaks existing behaviour: name the failing test,
what it expected and the relative path of the failing run's log, and leave
the test in place. The implementer's latest workflow check log predates this
run, so give the path printed by `dev-team check`.
