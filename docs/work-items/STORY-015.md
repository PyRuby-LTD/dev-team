---
id: STORY-015
type: story
title: Tester writes a few narrative tests, not one per criterion
parent: EPIC-006
workflow: default
step: publish
---
**As a** customer running dev-team
**I want** the tester to write a few narrative end-to-end tests rather than one per criterion
**So that** each story adds seconds, not minutes, to the workflow while the main journeys stay protected

## Context

`roles/tester.md` requires every acceptance criterion to have at least one
end-to-end test, and `prompts/test.md` repeats that and asks for a per-criterion
mapping. This is the main cause of slow, heavy suites. Only these two files
change; no Python and no existing tests.

## Acceptance Criteria

- [ ] **Given** `roles/tester.md`, **When** read, **Then** it no longer says every criterion needs an end-to-end test, and says the tester adds or extends a small number of narrative tests that each walk a realistic user journey through the real entry point, covering the happy paths of the story.
- [ ] **Given** `roles/tester.md`, **When** read, **Then** it says criteria better proven by unit tests are left to the implementer's unit tests and not duplicated, and that existing narrative tests are extended in preference to adding new ones.
- [ ] **Given** `prompts/test.md`, **When** read, **Then** it no longer requires a test per criterion, and the `## Tests` heading asks the tester to record which narrative tests cover the story's main journeys and which criteria are left to unit tests.
- [ ] **Given** `roles/tester.md`, **When** read, **Then** the existing rules on real entry points, canned data, few mocks, running tests only through the harness and not changing code under test are unchanged.
- [ ] **Given** `prompts/test.md`, **When** read, **Then** the instruction to "give each acceptance criterion at least one test" and the `written` condition "every criterion is covered" are reworded so that `written` means the narrative tests cover the story's main journeys and every criterion is either covered by one of them or recorded as left to unit tests; the `defect` guidance, the `{{...}}` placeholders and the `dev-team check` instructions are unchanged.
- [ ] No file other than `roles/tester.md` and `prompts/test.md` is changed, and `dev-team check` still passes.

## Analysis

Premise holds. `roles/tester.md` says "Cover every acceptance criterion with at least one such test", directly followed by "Unit tests of internal logic are the implementer's business; do not duplicate them". `prompts/test.md` says "Give each acceptance criterion in the item at least one test", asks under `## Tests` for "which test covers each criterion", and offers `written` only "when every criterion is covered".

What would change: the "Cover every acceptance criterion" paragraph in the role, and three passages in the prompt (the per-criterion instruction, the `## Tests` description, the `written` condition). The last is not named in the original criteria but would otherwise contradict the new wording, so criterion 4 above covers it.

Risk checked: no Python or test asserts on the wording of either file. `tests/test_launcher.py` only checks that both files exist in the harness checkout, so the change is safe for `dev-team check`. The "How you test" bullets in the role are untouched by the change.

Noted, out of scope: `prompts/review.md` says to approve "only when every criterion is met and proven". A reviewer may therefore ask for per-criterion tests the tester no longer writes. That is for the reviewer to judge against the tester's record of criteria left to unit tests; it could merit a follow-up story, but is not part of this one.

No questions for the customer.

## Challenge

Verdict: sound. A competent engineer could make this change as written and a reviewer could tell from the diff of two files whether they had. Nothing below changes what gets built or how it is judged; the analyst may tidy the first three or leave them.

Checked against the repository: the three quoted passages are in `roles/tester.md` and `prompts/test.md` as the Analysis says, and no test asserts on the wording being changed. `dev-team check` was not run, since nothing has changed yet.

1. **The risk check understates what the tests read, though the conclusion holds.** The Analysis says `tests/test_launcher.py` "only checks that both files exist". It also has `test_prompts_and_tester_brief_carry_the_checkout_command`, which requires the rendered test prompt and the tester brief to contain the harness command. Criteria 4 and 5 keep the harness instructions and the `{{...}}` placeholders unchanged, so the change is still safe; the implementer should simply know that deleting or rewording those lines would fail the suite.
2. **A criterion that is neither a happy path nor unit-provable has no stated home.** Criterion 1 has the narrative tests cover "the happy paths"; criterion 2 leaves to unit tests the criteria "better proven" there. A failure-path criterion that needs the running system (an exit code on bad input, say) fits neither. Criterion 5 forces every criterion into one of the two records, so the tester has to decide and the item is still implementable; the role text will leave that to the tester's judgement. That seems in keeping with the customer's "a few narrative tests", so I do not think it needs asking.
3. **Stale references in the Analysis.** "Criterion 4 above covers it" should read criterion 5. The reviewer conflict described as something that "could merit a follow-up story" is already STORY-018 (captured), and STORY-016 covers the implementer's side. Until STORY-018 is played, `roles/reviewer.md` still treats "a criterion with no test that would fail if it were broken" as unproven and prefers tests that run the real system, so reviews may bounce work for the reason this story removes. That is a sequencing point for the customer, not a defect in this item.
4. **"A small number" is not a number.** It is the customer's own phrasing ("a few") and the deliverable is guidance to an agent, not a threshold, so it is verifiable as wording. Noted only so nobody mistakes it for an oversight.

Scope traces cleanly: every criterion serves the stated outcome or guards the boundary set by EPIC-006 (roles and prompts only, no Python, no existing tests).

## Feedback

- **analyse -> analysis:** This is a focused story, only changing agent roles / prompts. Avoid overthinking this
- **play -> implement:** DO NOT CREATE ANY TESTS - this change should not result in new tests being added as it is just the .md files that are impacted.

## Implementation

Updated `roles/tester.md` to require a small number of narrative tests through
real entry points covering the story's happy paths, prefer extending existing
narrative tests, and leave criteria better proven by unit tests to the
implementer's tests without duplication. The existing testing safeguards and
harness instructions are unchanged.

Updated `prompts/test.md` to request narrative coverage of the main journeys,
record narrative coverage and criteria left to unit tests under `## Tests`,
and choose `written` only when the main journeys are covered, every criterion
is covered by a narrative test or recorded as left to unit tests, and the suite
passes. Defect guidance and placeholders are unchanged. No Python or test files
were changed, and no tests were added, as requested by the latest feedback.
Only the two specified product files changed; this item and evidence logs are
the required workflow records.

Checks:

- `.venv/bin/python -m unittest discover -s tests -p test_launcher.py`:
  initial run failed (45 tests, 25 failures, 2 errors) because subprocesses
  could not write to the default uv cache in this sandbox. Evidence:
  `backlog/log/STORY-015/unit-launcher.log`.
- Repeated the same direct test command with
  `UV_CACHE_DIR=/tmp/devteam-story-015-uv-cache`: all 45 tests passed. Evidence:
  `backlog/log/STORY-015/unit-launcher-writable-cache.log`.
- `git diff --check`: passed. Evidence:
  `backlog/log/STORY-015/diff-check.log`.
- `dev-team check` with the writable uv cache: failed (275 tests, one
  failure), in `test_tui.Acting.test_failed_agent_is_shown_and_can_be_retried`:
  the expected agent-failure message was absent from the displayed card.
  Evidence: `backlog/log/check/20261009T123326900918.log`.
- `.venv/bin/python -m unittest discover -s tests -p test_tui.py -k test_failed_agent_is_shown_and_can_be_retried`
  with the writable uv cache: passed (one test). The full-suite failure did
  not reproduce in isolation; no out-of-scope TUI code or test was changed.
  Evidence: `backlog/log/STORY-015/unit-tui-retry.log`.
- Repeated `dev-team check` with the writable uv cache: passed, all 275
  tests. Evidence: `backlog/log/check/20261009T123753159547.log`.

All acceptance criteria are implemented. No blocked work remains. Changes
are left in the working tree; no commit was made.

## Tests

No tests were added. The latest customer feedback (play -> implement) says this
change must not produce new tests, and the story changes only `roles/tester.md`
and `prompts/test.md`, so there is no running behaviour for a narrative test to
walk. Existing tests that read these files (`tests/test_launcher.py`, including
the check that the rendered test prompt and tester brief carry the harness
command) already protect the parts that must stay unchanged.

Criteria left to review of the diff rather than to tests: all six, since they
concern the wording of the two markdown files.

Run one test on its own, for example:
`dev-team check test_launcher`

Whole suite: `dev-team check` passed (275 tests), log
`backlog/log/check/20261009T124616393507.log`. An earlier run failed once in
`test_tui.Acting.test_failed_agent_is_shown_and_can_be_retried` (log
`backlog/log/check/20261009T124209248486.log`); the same test also failed once
for the implementer and then passed on rerun, so it looks timing-dependent and
unrelated to this story.

## Test run

Run by the harness, 2026-10-09 12:52:16 UTC: passed (exit 0); duration 128.242 seconds.

## Review

No blocking findings. Minor observations, none requiring a change:

1. `prompts/test.md` now tells the tester to "leave criteria better proven by unit tests to the implementer's unit tests" in the opening paragraph, and `written` requires every criterion to be covered or recorded as left to unit tests. A failure-path criterion needing the running system fits neither bucket explicitly; the tester must judge. This matches the customer's "a few" framing, as the Challenge noted.
2. No test asserts on the new wording. That is deliberate per the customer's "do not create any tests" feedback, so the wording criteria are proven by diff inspection only.
3. `roles/reviewer.md` still treats a criterion without a failing-if-broken test as unproven; this is STORY-018 and out of scope here.

Criteria satisfied:

- C1: `roles/tester.md` drops "Cover every acceptance criterion with at least one such test" and adds narrative tests, each walking a realistic journey through the real entry point and covering the story's happy paths.
- C2: same paragraph leaves criteria better proven by unit tests to the implementer without duplication, and prefers extending existing narrative tests.
- C3: `prompts/test.md` no longer requires a test per criterion; the `## Tests` instruction asks for which narrative tests cover the main journeys and which criteria are left to unit tests.
- C4: the diff of `roles/tester.md` touches only that one paragraph; the "How you test" rules and the code-under-test rule are untouched.
- C5: "give each acceptance criterion at least one test" is reworded, and `written` now means the main journeys are covered and every criterion is covered or recorded as left to unit tests. The `defect` guidance, the `{{harness_command}}` and `{{verify_log}}` placeholders and the check instructions are unchanged in the diff.
- C6: `git diff main...devteam/STORY-015 --stat` lists only those two files. The harness's full suite passed (275 tests, exit 0): `backlog/log/STORY-015/verify-20261009T125008677036.log`.
