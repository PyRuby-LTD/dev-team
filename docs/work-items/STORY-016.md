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

## Implementation

Updated `roles/implementer.md` to make the implementer the main author of
tests below end-to-end level, using judgement about which criteria merit unit
tests. Retained the rules about plumbing, plain code and mocks, and added the
prose exemption and guidance about adapting existing tests. Default test runs
now cover changed tests and modified modules, plus tests named in returned
findings. Other project checks still run, and the role describes later
full-suite runs and returned failures without specifying a workflow route.

Updated `prompts/implement.md` to require a coverage decision for each
criterion under `## Implementation`, including a reason when no test is
provided. Retained direct unit-test execution and the full-suite timing.

Acceptance-criterion coverage notes (numbered in the order above):

1. No unit test: this is role prose; checked by reading the ownership wording.
2. No unit test: this is role prose; checked the precedence, mock guidance and
   delegation of running-system criteria to the tester's narrative tests.
3. No unit test: this is role prose; checked judgement, the prose exemption and
   the options for extending or reworking existing tests.
4. No unit test: this is role prose; checked default targeted runs and re-running
   tests named in tester defects or review findings.
5. No unit test: this is role prose; checked later full-suite execution and
   returned failures without a workflow step or route.
6. No unit test: this is prompt prose; checked the three coverage choices, the
   reason note and the retained unit-test and full-suite instructions.
7. No unit test: this is role prose; checked that other project checks and
   reporting failures with captured evidence remain required.
8. No unit test: this is a file-scope constraint; checked the diffs. Only the
   two specified markdown files and this item body changed; evidence is saved
   in the backlog logs. Whole-suite proof remains with workflow verification.

Checks and results:

- Direct unit-test run via `uv run python -m unittest` selecting
  `tests.test_run_evidence.TestStoryFromStartToPublication.test_no_prompt_or_brief_tells_an_agent_to_read_or_paste_test_output_in_the_item`
  and `tests.test_launcher.AgentsReachTheHarness.test_prompts_and_tester_brief_carry_the_checkout_command`:
  initial attempt failed before tests started (exit 2), because the default uv
  cache was read-only. Evidence: `backlog/log/STORY-016/targeted-tests.log`.
  Retried with `UV_CACHE_DIR=/tmp/story-016-uv-cache`: both tests passed
  (exit 0). Evidence: `backlog/log/STORY-016/targeted-tests-retry.log`.
- `git diff --check`: passed (exit 0).
  Evidence: `backlog/log/STORY-016/diff-check.log`.
- No workflow check log existed to read. Did not run `dev-team check` or the
  full suite, as criterion 8 reserves that proof for workflow verification.
  The project provides no separate lint, type-check or build check target.

No criteria are blocked. As noted in the Challenge, the README sentence about
testing only difficult logic remains stale; changing it is outside criterion 8.

## Tests

Narrative test: `tests.test_launcher.AgentsReachTheHarness.test_implement_step_hands_the_agent_judgement_led_unit_testing_and_targeted_runs`
builds the implementer's brief and the rendered `implement` prompt through the
same `config.load_roles` and `render` paths the launcher uses, and checks what
the agent is handed: tests for criteria owned by the implementer with the
prose and plain-code exemptions, extending or reworking existing tests,
targeted runs by default with re-runs of tests named in findings, the full
suite run later, other project checks still run, the three-way coverage record
with a reason, and that the old "relaxed approach", "tester's job" and "run
whatever tests or checks" wording is gone. It covers criteria 1 to 7 at the
level of key phrases. The implementer is a codex role, for which the suite has
no stub, so the test stops short of launching it.

Left to reading the files: the precise sense of each criterion (wording
quality), and criterion 8 (file scope), which is a diff matter and is not a
behaviour of the running system.

Run one test: `dev-team check tests.test_launcher.AgentsReachTheHarness.test_implement_step_hands_the_agent_judgement_led_unit_testing_and_targeted_runs`.
The whole suite passed (276 tests): `backlog/log/check/20261009T133037424915.log`.

## Test run

Run by the harness, 2026-10-09 13:34:22 UTC: passed (exit 0); duration 107.200 seconds.

## Review

No blocking findings. Every criterion is met and the wording is pinned by a passing test.

Evidence: the harness ran the whole suite on this branch (276 tests, exit 0): `backlog/log/STORY-016/verify-20261009T133234970639.log`.

Notes, most significant first:

1. Criterion 8 says only the two markdown files and the item record change; the diff also adds `tests/test_launcher.py::test_implement_step_hands_the_agent_judgement_led_unit_testing_and_targeted_runs`. It comes from the tester's step, is additive, and is what proves criteria 1 to 7, so I do not treat it as scope creep. The customer may want criterion 8 read as excluding the tester's narrative test.
2. The pinning test checks key phrases, so it would pass a rewording that kept the phrases but changed the sense. That is the limit of what a phrase check can show. I read the files for the sense.
3. The `README.md` sentence "writes unit tests only where the logic is hard to get right" is now stale. It was flagged in the Challenge and is correctly left alone under criterion 8.

Criteria satisfied:

1. `roles/implementer.md`: "main author of tests for acceptance criteria that can be proven below the end-to-end level"; the "automation tester's job" sentence is removed. Test asserts the phrase and the absence.
2. Mocks and plumbing/plain-code guidance kept; "That rule takes precedence ... such a criterion needs no unit test"; criteria needing the running system are left to the tester's narrative tests.
3. "relaxed approach" and "only where logic is hard" are gone. The role expects a unit test for each criterion worth proving, with judgement, and says prose changes (prompt or role markdown) need none. For code changes, an added assertion or a reworked superseded test may serve better.
4. "By default, run the tests you wrote or changed and the tests of the modules you modified, not the full test suite", plus re-running tests named in a tester defect or review finding.
5. "The full suite is run later; failures that are yours to fix are passed back to you", with no workflow step or route named.
6. `prompts/implement.md` asks, per criterion, for unit-tested, left to narrative tests, or no test and why, with the reason as a note under the heading. "Run your unit tests directly; the full suite is run for you after the tester's step" is kept.
7. "Run whatever tests or checks" is replaced. Only the test-suite part is narrowed; linters, type checks and builds still run; results including failures are reported with output kept in the evidence logs.
8. Met in substance. See note 1.
