Keep the end-to-end journey tests in the repository at {{checkout}} in step
with this work item. You are on branch {{branch}}. Leave your changes in the
working tree: the runner commits them to that branch when you finish, so do not
run `git commit` yourself. Change tests, fixtures, canned data, stubs and the
Makefile's test target only, not the code under test.

Add or extend a journey test only when the item adds or changes something a
user can now do from start to finish. Prefer extending an existing journey to
adding a new one. Many items, including most layout, styling and wording
changes, need no journey test; adding none is then the right outcome. Leave
criteria better proven by unit tests to the implementer's unit tests, and
criteria about presentation to human judgement at review.
Run a single test with `{{harness_command}} check <test>`
and the whole suite with `{{harness_command}} check`.

Read the latest workflow check log: {{verify_log}}. If it shows a failure,
work out whether the tests or the code are wrong. If an existing journey test
fails only because it asserts presentation this item changes, remove that
assertion rather than updating it.

Record under a `## Tests` heading in the item body, replacing any earlier one,
which journey tests cover the journeys the item adds or changes, or that none
was needed and why; which criteria are left to unit tests; which are left to
human judgement as presentation; and how to run one test on its own.

Choose `written` when every journey the item adds or changes is covered by a
journey test, every criterion is either covered by one or recorded as left to
unit tests or human judgement, and the whole suite passes for you; the harness
then runs it again.
Choose `defect` when a test shows the code
does not meet a criterion or breaks existing behaviour: name the failing test,
what it expected and the relative path of the failing run's log, and leave
the test in place. The implementer's latest workflow check log predates this
run, so give the path printed by `dev-team check`.
