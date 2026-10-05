Add integration tests for this work item to the regression suite in the
repository at {{checkout}}. You are on branch {{branch}}. Leave your changes in
the working tree: the runner commits them to that branch when you finish, so do
not run `git commit` yourself. Change tests, fixtures, canned data and stubs
only, not the code under test.

Give each acceptance criterion in the item at least one test that exercises the
running system. Then run the whole suite.

Record under a `## Tests` heading in the item body, replacing any earlier one:
which test covers each criterion, how to run the suite, and its actual output.

Choose `tested` when every criterion is covered and the whole suite passes.
Choose `defect` when a test shows the implementation does not meet a criterion
or breaks existing behaviour: name the failing test, its output and what it
expected.
