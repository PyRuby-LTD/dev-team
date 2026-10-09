---
id: STORY-016
type: story
title: Implementer owns unit-level proof of criteria
parent: EPIC-006
workflow: default
step: publish
---
**As a** customer running dev-team
**I want** the implementer to own unit-level proof of the acceptance criteria
**So that** behaviour is verified cheaply and close to the code, leaving end-to-end tests for the tester's narratives

## Context

`roles/implementer.md` currently asks for a relaxed approach to unit tests and
says proving the criteria is the tester's job. Under the new approach the
implementer is the main author of tests for criteria. Only `roles/implementer.md`
and `prompts/implement.md` change.

## Acceptance Criteria

Question 1 is answered: the implementer uses judgement and is not required to write a test for every criterion. Criteria 1 to 3 and 6 reflect that answer.

- [ ] **Given** `roles/implementer.md`, **When** read, **Then** it makes the implementer the main author of tests for the acceptance criteria that can be proven below the end-to-end level, and no longer says proving the criteria is the tester's job.
- [ ] **Given** `roles/implementer.md`, **When** read, **Then** it keeps the guidance to avoid mocks where sensible and not to test plumbing or restate what the code plainly does, says that rule takes precedence where a criterion is met only by plumbing or plain code (such a criterion needs no unit test), and says criteria that need the running system are left to the tester's narrative tests.
- [ ] **Given** `roles/implementer.md`, **When** read, **Then** it no longer tells the implementer to "take a relaxed approach to unit tests" or to write tests only where logic is hard; it instead expects a unit test for each criterion worth proving at unit level, using judgement, and says that a criterion needs no unit test where the change is prose (such as a prompt or role markdown file), and that for code changes an assertion added to an existing test, or reworking a test the change supersedes, may serve better than a new test.
- [ ] **Given** `roles/implementer.md`, **When** read, **Then** it tells the implementer that by default they run the tests they wrote or changed and the tests of the module(s) they modified, not the full test suite, and that they also re-run any test named in findings passed back to them (a tester defect or a review finding) to confirm the fix.
- [ ] **Given** `roles/implementer.md`, **When** read, **Then** it says the full suite is run later, and that failures which are the implementer's to fix are passed back to them, without naming a specific workflow step or route.
- [ ] **Given** `prompts/implement.md`, **When** read, **Then** the `## Implementation` record asks, for each acceptance criterion, whether it is covered by a unit test, left to the tester's narrative tests, or has no test and why (the reason is written as a note under the `## Implementation` heading so the tester and reviewer can challenge the decision or add their own test); and it still states that the implementer runs unit tests directly and that the full suite is run after the tester's step.
- [ ] **Given** `roles/implementer.md`, **When** read, **Then** "run whatever tests or checks the project provides" is replaced so that only the test-suite part is narrowed (per the targeted-run criterion) while other project checks (linters, type checks, builds) still run, and results including failures are still reported with captured output kept in the evidence logs.
- [ ] Only `roles/implementer.md`, `prompts/implement.md` and this work item's record change. Whole-suite proof that `dev-team check` passes is supplied by the workflow's verify step; the implementer is not expected to run it.

## Analysis

Findings from reading the repository:

Revised after the challenge:

- `roles/implementer.md` today has three relevant passages: "Take a relaxed approach to unit tests..." (write only for hard logic), "Proving the acceptance criteria against the running system is the automation tester's job... do not build that suite", and "Run whatever tests or checks the project provides, and report their results". The last covers linters, builds and the test suite alike.
- `prompts/implement.md` already says "Run your unit tests directly; the full suite is run for you after the tester's step." That is the right home for the workflow fact; the role file stays workflow-agnostic. In `workflows/default.json`, `verify` fails to `test`, not `implement`; the tester decides whether it is a `defect`. So the role must not say failures come straight back.
- The implement step is also entered via `defect` from `test` and `revise` from `review`. The failing test is often a tester's narrative test, so the targeted-run rule must include tests named in passed-back findings. The customer's feedback said "by default", not "only".
- The prompt's `## Implementation` instruction asks only for changes, checks and results; the coverage split is new. `roles/tester.md` (as changed by STORY-015, on `devteam/STORY-015` and not yet on `main`) leaves anything not in a narrative to "the implementer's unit tests", so the record needs a third state, "no test, and why", or a criterion can fall between the two.
- The project's full suite is `make regression`; a module run is `make regression TEST=tests.test_x`. The role file stays project-agnostic and names neither.
- No test pins the wording of either file: `tests/test_run_evidence.py` only scans roles and prompts for prohibited evidence phrases, and `tests/test_launcher.py` does not render `implement`.
- The role wording is not the only cause of repeated full-suite runs. The implementer log for STORY-015 (`backlog/log/STORY-015/implement-20261009T123222225246.log`) shows many full-suite invocations for a two-file wording change, but every agent prompt also ends with the `## Run evidence` block from `devteam/runner.py`, which names `dev-team check` and nothing narrower; that is outside this epic's boundary. Neither file tells the implementer how to run a single test, unlike the tester. The change is expected to reduce the repeat runs, not necessarily end them. Smallest check afterwards: count check logs written during the next implement step.

Customer answer to Question 1 (judgement, not a mandatory test per criterion) is incorporated into criteria 1, 3 and 6; no open questions remain.

Assumptions: "tester's narrative tests" is the accepted name for end-to-end tests; "module" means the code unit the implementer edited and its tests, left to their judgement; the customer's feedback extends this story and is folded in above. Criteria are checkable by reading the two files.

## Questions

1. Must the implementer write a unit test for every acceptance criterion that can be proven below end-to-end level, or should they use judgement and record, per criterion, whether it is unit-tested, left to the tester's narrative tests, or has no test and why (for example a wording change met by plain code)? The request says the implementer should do "a bit more of the testing at unit test level"; a mandatory test per criterion would be a stronger rule and sits awkwardly with not testing plumbing. We recommend judgement with the three-way record.

   **Answer:** No, the implementer does not have to write a test for every AC and should exercise judgement. Some changes (such as updating prompt text or a role markdown file) should not have any unit tests added. Some python code changes could be better tested by adding an assertion to an existing test or reworking a test that this change supercedes. When ACs are not unit tested, a comment under the implementation header saying why gives the tester and reviewer the chance to decide whether to challenge the decision or add to their own test

## Challenge

Verdict: sound. A competent engineer could implement the item as written and a reviewer could tell from the two files whether they had. The findings of the earlier challenge are all addressed, and the customer's answer to Question 1 is carried faithfully into criteria 1, 3 and 6. Three notes follow; none changes what is built.

Checked against the repository: the three passages quoted from `roles/implementer.md` and the sentence quoted from `prompts/implement.md` are there as the Analysis says. `workflows/default.json` routes `verify` failures to `test`, and enters `implement` from `test` (`defect`) and `review` (`revise`), which is what criteria 4 and 5 rely on. No test pins the wording of either file: `tests/test_run_evidence.py` scans roles and prompts only for three prohibited evidence phrases, and `tests/test_launcher.py` renders `test`, `review` and `product-owner`, not `implement`. The STORY-015 implementer log cited in the Analysis exists. `dev-team check` was not run, since nothing has changed yet.

Traced to the customer's own words: judgement over a test per criterion, no unit tests for prose changes, an added assertion or reworked test in place of a new one, and the "no test, and why" note under `## Implementation` all come from the answer to Question 1. Targeted runs "by default", and the full suite run later with failures passed back, come from the feedback entry. The two-file scope is the epic boundary.

1. **`README.md` will restate the rule this story removes, and criterion 8 forbids fixing it.** Line 153 of `README.md` says "The implementer writes unit tests only where the logic is hard to get right". Once the role changes that sentence is untrue, and the Analysis does not mention it. The item is right to leave it alone: the epic boundary is roles and prompts only, and widening it is the customer's call, not the team's. The customer should know when deciding to play that one README sentence is left stale, and may want it picked up in a follow-up or by widening criterion 8 by that one line. Not a reason to hold the story.

2. **One inference to be aware of, not the customer's words.** Criterion 4's "also re-run any test named in findings passed back to them" is the team's addition, made in answer to the earlier challenge. The customer said only that the full suite should not be the default. It is consistent with that and with `prompts/implement.md` ("if its `## Tests` section reports a defect, fix the code"), and without it the implementer could not confirm a fix, so it stands; it is simply not something the customer said.

3. **Stale fact in the Analysis, no effect on the criteria.** The Analysis says the STORY-015 change to `roles/tester.md` is "on `devteam/STORY-015` and not yet on `main`". It has since been merged; `roles/tester.md` on `main` now reads "Leave criteria better proven by unit tests to the implementer's unit tests". The term "narrative tests" is therefore established where this story branches from, which removes the earlier concern.

The cheapest way to be wrong is already named in the Analysis and still holds: the role wording may not be the only thing driving repeat full-suite runs, because the `## Run evidence` block in `devteam/runner.py` names `dev-team check` and nothing narrower, and that Python is outside the epic. The item claims a reduction, not an end. Smallest check: count the check logs written during the next implement step after this story is merged.

## Feedback

- **analyse -> analysis:** An additional consideration is the implementer shouldn't run the full test suite as a default position. Running tests they create or in the module they are updating is sensible. The full test suite is run in a later step and failures passed back to implement and at the moment the full suite is being run too many times even for small isolated changes.
- **rejected -> rejected:** def test_implement_step_hands_the_agent_judgement_led_unit_testing_and_targeted_runs(self): This is a poor test that just asserts on content of a role. It makes the code brittle and changes harder without giving any real assurances.

## Implementation

Addressed the latest customer feedback by removing
`tests/test_launcher.py::test_implement_step_hands_the_agent_judgement_led_unit_testing_and_targeted_runs`.
It asserted phrases in role and prompt prose, making wording changes brittle
without proving behaviour. No replacement wording test was added. The earlier
Tests and Review sections describe that removed test and are historical.

Read `roles/implementer.md` and `prompts/implement.md`: they already meet
criteria 1–7, so no further wording changes were needed. The existing changes
make the implementer responsible for worthwhile unit-level proof, allow
judgement and prose/plumbing exemptions, recommend real collaborators and
adapting existing tests, require targeted runs and rerunning named findings,
retain other project checks and evidence reporting, and require the three-way
coverage record. The role remains workflow-agnostic; the prompt retains the
full-suite timing.

Acceptance-criterion coverage notes (numbered in the order above):

1. No unit test: role prose; ownership and removal of the tester-ownership rule
   were checked by reading the file.
2. No unit test: role prose; mock guidance, plumbing/plain-code precedence and
   delegation to the tester's narrative tests were checked by reading.
3. No unit test: role prose; judgement, prose exemptions and adapting existing
   tests were checked by reading; the old relaxed/hard-logic-only rule is gone.
4. No unit test: role prose; default targeted runs and rerunning tests named in
   tester defects or review findings were checked by reading.
5. No unit test: role prose; later full-suite execution and returned failures
   were checked by reading, with no workflow step or route specified.
6. No unit test: prompt prose; all three coverage choices, the reason note and
   retained direct-unit-test/full-suite timing instructions were checked by reading.
7. No unit test: role prose; other checks and reporting failures with captured
   evidence remain required, as checked by reading.
8. No unit test: file-scope constraint, checked by inspecting the diff. This
   revision removes the tester-added test specifically rejected by the customer,
   restoring the story's overall scope to the two markdown files and item record.
   Evidence logs are saved separately. Whole-suite proof remains with verification.

Checks and results:

- Read the latest workflow log,
  `backlog/log/STORY-016/verify-20261009T133234970639.log`: the prior full suite
  passed (276 tests, exit 0). This is existing workflow evidence, not a new run.
- Re-ran the exact test named in the customer finding before deleting it,
  using `.venv/bin/python -m unittest
  tests.test_launcher.AgentsReachTheHarness.test_implement_step_hands_the_agent_judgement_led_unit_testing_and_targeted_runs`:
  passed (1 test, exit 0). Evidence:
  `backlog/log/STORY-016/rejected-test-before-removal.log`. Its passing result
  does not address the customer's objection to the test's value; removal does.
- Direct affected-module run, `.venv/bin/python -m unittest tests.test_launcher`:
  failed (45 tests, 25 failures and 2 errors, exit 1) because launcher subprocesses
  could not write to the default uv cache. Evidence:
  `backlog/log/STORY-016/launcher-tests-after-removal.log`.
  Retried the same command with `UV_CACHE_DIR=/tmp/story-016-uv-cache`:
  passed (45 tests, exit 0). Evidence:
  `backlog/log/STORY-016/launcher-tests-after-removal-retry.log`.
- `git diff --check` and `git -C backlog diff --check`: passed (exit 0).
  Evidence: `backlog/log/STORY-016/revision-diff-check.log`.
- Inspected the removal and updated item diffs. Evidence:
  `backlog/log/STORY-016/revision-code-diff.log` and
  `backlog/log/STORY-016/revision-item-diff.log`.
- No new unit tests: the acceptance criteria are prose and scope checks; the
  customer explicitly rejected the phrase-pinning test. No narrative suite was added.
- Did not run `dev-team check` or the full suite, as criterion 8 leaves that
  proof to workflow verification. The Makefile provides only regression testing;
  there are no separate configured lint, type-check or build check targets.

No criteria are blocked. The README's hard-logic-only sentence remains outside
scope, as already noted in the Challenge and Review. No PR comments require
further changes.

## Tests

No narrative test added. Every criterion is a statement about the wording of
`roles/implementer.md` or `prompts/implement.md`, or about which files change.
None describes behaviour of the running system, and the customer rejected the
earlier phrase-pinning test as brittle without real assurance, so it stays
removed and nothing replaces it. Existing narrative tests are unaffected.

Left to reading the files: criteria 1 to 7 (role and prompt prose) and
criterion 8 (file scope, a diff matter). The implementer's record gives a
"no unit test, and why" note for each.

Run one test on its own: `dev-team check <module.Class.test_name>`, for example
`dev-team check tests.test_run_evidence`.
The whole suite passed (275 tests): `backlog/log/check/20261009T144100641311.log`.

## Test run

Run by the harness, 2026-10-09 14:44:51 UTC: passed (exit 0); duration 106.532 seconds.

## Review

No blocking findings. Every criterion is met by the wording in the two files. Evidence: the harness ran the whole suite on this branch (275 tests, exit 0): `backlog/log/STORY-016/verify-20261009T144305234727.log`.

Notes, most significant first:

1. The earlier review described a phrase-pinning test in `tests/test_launcher.py`. The customer rejected it and it is gone: the diff against `main` touches only `roles/implementer.md`, `prompts/implement.md` and the item record (`docs/work-items/STORY-016.md`). Criteria 1 to 7 therefore rest on reading the files, which is what the customer asked for; no test would fail if the wording regressed. That is accepted, not a defect.
2. The `README.md` sentence "writes unit tests only where the logic is hard to get right" is now stale. It was flagged in the Challenge and is correctly left alone under criterion 8.

Criteria satisfied (read from `git diff main...devteam/STORY-016`):

1. `roles/implementer.md`: "main author of tests for acceptance criteria that can be proven below the end-to-end level"; the "automation tester's job" sentence is removed.
2. Mock avoidance and the plumbing/plain-code rule are kept; "That rule takes precedence ... such a criterion needs no unit test"; criteria needing the running system are left to the tester's narrative tests.
3. "relaxed approach" and "only where logic is hard" are gone. A unit test is expected for each criterion worth proving, with judgement. Prose changes (prompt or role markdown) need none. For code, an added assertion or a reworked superseded test may serve better.
4. "By default, run the tests you wrote or changed and the tests of the modules you modified, not the full test suite"; re-run tests named in a tester defect or review finding.
5. "The full suite is run later; failures that are yours to fix are passed back to you", naming no step or route.
6. `prompts/implement.md` asks per criterion for unit-tested, left to narrative tests, or no test and why, with the reason as a note under the heading. Line 7 still says "Run your unit tests directly; the full suite is" run after the tester's step.
7. "Run whatever tests or checks" is replaced; only the test suite is narrowed, linters, type checks and builds still run, and results including failures are reported with output in the evidence logs.
8. Only the two files and the item record change.

## Pull request

https://github.com/PyRuby-LTD/dev-team/pull/13

## Pull request feedback

There are no comments on this pull request.
