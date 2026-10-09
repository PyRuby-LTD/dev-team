---
id: STORY-018
type: story
title: Reviewer accepts unit or narrative tests as proof
parent: EPIC-006
workflow: default
step: publish
---
**As a** customer running dev-team
**I want** the reviewer to judge criteria as proven by unit or narrative tests as appropriate
**So that** review does not send work back for lacking a dedicated end-to-end test per criterion

## Context

`roles/reviewer.md` says a criterion with no test that would fail if it were
broken is unproven, and favours tests that run the real system. Under the new
approach a criterion may legitimately be proven by an implementer's unit test.
Only `roles/reviewer.md` and `prompts/review.md` change.

## Acceptance Criteria

- [ ] **Given** `roles/reviewer.md`, **When** read, **Then** a criterion counts as proven if a test at any level that would fail were it broken covers it (a unit test or a tester's narrative test included), and the reviewer does not require an end-to-end test for every criterion.
- [ ] **Given** `roles/reviewer.md`, **When** read, **Then** the rule that a test which mocks the thing it claims to prove is not evidence is retained.
- [ ] **Given** `prompts/review.md`, **When** read, **Then** for each criterion it asks the reviewer to name the test that proves it (unit or narrative) or, where the implementer recorded that there is no test, to state that recorded reason and whether they accept it.
- [ ] **Given** `roles/reviewer.md`, **When** read, **Then** it no longer says "the strongest evidence runs the real system", and it does not rank narrative tests above unit tests as evidence.
- [ ] **Given** `roles/reviewer.md`, **When** read, **Then** it states the principle that a criterion for which the implementer gave a reason for having no test (for example the change is prose, or plumbing) is judged on that reason: the reviewer either accepts it, in which case the criterion counts as proven for the purpose of approval, or says why the criterion needs a test. Absence of a test is not unproven by default.
- [ ] **Given** `prompts/review.md`, **When** read, **Then** it carries the workflow detail: the reviewer may read the implementer's per-criterion test record under `## Implementation` (covered by a unit test, left to narratives, or no test and why). This is the one exception to "Judge the code, not the `## Implementation` notes"; the implementer's account of what they changed is still not evidence.
- [ ] **Given** `roles/reviewer.md`, **When** read, **Then** its opening statement that the reviewer does not have the implementer's account and should not go looking for it is amended so it does not contradict the exception in the previous criterion, and it does not name the `## Implementation` heading.
- [ ] **Given** `prompts/review.md`, **When** read, **Then** the approve rule reads that `approve` is chosen only when every criterion is met and either proven by a test or accepted without one on its recorded reason; `revise` remains the choice otherwise, including an empty diff.
- [ ] **Given** `prompts/review.md`, **When** read, **Then** the instruction to name the proving test sits alongside the existing instruction to list satisfied criteria with evidence, and all existing placeholders (`{{branch}}`, `{{checkout}}`, `{{base}}`, `{{verify_log}}`, `{{harness_command}}`) and the rest of the prompt are unchanged.
- [ ] Only `roles/reviewer.md`, `prompts/review.md` and this work item's record change. Whole-suite proof that `dev-team check` passes is supplied by the workflow's verify step.

## Analysis

Premise confirmed. In `roles/reviewer.md` the "Claims without evidence" bullet says: a criterion with no test that would fail if broken is unproven; a test that mocks the thing it proves is a claim; "the strongest evidence runs the real system". That last clause is what pushes the reviewer to demand end-to-end tests, and is the only wording that conflicts with the story. The "would fail if broken" test and the mock rule are already level-neutral and stay.

`prompts/review.md` currently asks only for "the criteria you found satisfied, with the evidence for each"; it does not ask for a named test. It uses placeholders that `tests/test_requests.py` renders, so they must survive the edit. No test reads the wording of either file, so no code or test change is needed.

Two further passages conflict with the story. `roles/reviewer.md` lines 3-4 say the reviewer does not have the implementer's account "and should not go looking for it", and `prompts/review.md` line 3 says "Judge the code, not the `## Implementation` notes". The story needs the reviewer to read the implementer's reason for an untested criterion, so both need a narrow exception. `prompts/review.md` line 15 says to approve "only when every criterion is met and proven"; with an accepted no-test reason standing in for a test, that wording must change (criterion 8) or prose-only stories like this one could never be approved.

Source of the recorded reasons: the customer's answer to Question 1 of `backlog/stories/STORY-016.md` says that when criteria are not unit tested, "a comment under the implementation header saying why gives the tester and reviewer the chance to decide whether to challenge the decision". The instruction to record this lives in `prompts/implement.md`; `roles/implementer.md` makes the implementer the main author of unit tests. `roles/tester.md` writes narrative tests and leaves unit-level criteria alone.

Resolution of the earlier challenge: the exception to the "do not read the notes" sentences is limited to the per-criterion test record (criteria 6 and 7); the heading reference sits in `prompts/review.md`, with the role file stating only the principle (criteria 5 and 7); the proving-test instruction has a branch for recorded reasons (criterion 3); "any level" replaces "unit or narrative" (criterion 1); the approve rule is reworded and no longer claimed unchanged (criterion 8).

Assumptions stated, not asked: the bar stays "a test would fail were the criterion broken"; only the level is relaxed. The customer's wording supports the reviewer reading and challenging the reason; that an accepted reason is sufficient for approval is the natural consequence of "decide whether to challenge", and is assumed. No customer questions outstanding.

## Challenge

Verdict: sound. A competent engineer could make the two edits as written, and a reviewer could tell by reading `roles/reviewer.md` and `prompts/review.md` whether each criterion is met. The six findings of the earlier challenge are all resolved in the criteria. Checked by reading `roles/reviewer.md`, `prompts/review.md`, `prompts/implement.md`, `prompts/test.md`, `roles/implementer.md`, `roles/tester.md`, `workflows/default.json`, `tests/test_requests.py`, `backlog/epics/EPIC-006.md` and `backlog/stories/STORY-016.md`; no commands were run beyond reading and searching, and `dev-team check` was not run.

Claims checked against the repository, all of which hold:

- The quoted wording is present verbatim: "the strongest evidence runs the real system" and "should not go looking for it" in `roles/reviewer.md`; "Judge the code, not the `## Implementation` notes" and "only when every criterion is met and proven" in `prompts/review.md`.
- The five placeholders named in criterion 9 are exactly those `prompts/review.md` uses.
- `prompts/implement.md` asks for the three-way per-criterion record under `## Implementation`, addressed to "the tester and reviewer", which is the record criterion 6 lets the reviewer read.
- The customer's answer to Question 1 of `backlog/stories/STORY-016.md` reads as the Analysis quotes it.
- No test pins the wording of either file: `tests/test_requests.py` compares the rendered review prompt with the file's own contents.
- The scope stays inside the EPIC-006 boundary of roles and prompts, and the reviewer role is used only by the `review` step of `workflows/default.json`, so no other workflow is affected.

One inference remains, and the customer should see it before playing the item. The customer said the note lets the reviewer "decide whether to challenge the decision"; they did not say that an unchallenged reason is enough to approve. Criteria 5 and 8 rest on that step, and the Analysis labels it as assumed. I do not think it needs asking: the customer also said prompt and role changes "should not have any unit tests added", and `roles/implementer.md` now says so, so if an accepted reason could not stand in for a test, no prose-only story (this one included) could ever be approved. If the customer disagrees, the cheapest check is one question: "When the reviewer accepts the implementer's recorded reason for a criterion having no test, may they approve without a test for that criterion?"

Two points of wording for the implementer to read with care; neither changes what is built:

1. The last sentence of criterion 5, "Absence of a test is not unproven by default", read alone would contradict the retained rule that a criterion with no test that would fail if it were broken is unproven. The rest of criterion 5 and criterion 8 settle the scope: it applies only where the implementer recorded a reason. A criterion with neither a test nor a recorded reason stays unproven and the choice is `revise`.
2. "The rest of the prompt are unchanged" in criterion 9 means the rest apart from the edits criteria 3, 6 and 8 require, since those criteria change line 3 and the approve rule.

## Implementation

Implemented the reviewer role and prompt changes. The role now accepts proving
tests at any level, retains the rule against mocks of the thing being proved,
and judges recorded no-test reasons explicitly. The prompt permits reading only
the implementer's per-criterion test record as an exception to ignoring their
implementation account, asks for named proving tests or a decision on recorded
reasons, and updates the approval rule. All five placeholders and the prompt's
remaining instructions are preserved. No code or tests were changed.

Checks and evidence:

- `dev-team check tests.test_requests`: passed, 9 tests. Full captured output:
  `backlog/log/check/20261009T150024661128.log`.
- `git diff --check`: passed. Evidence:
  `backlog/log/STORY-018/diff-check.log`.
- Read the final diff against all ten criteria and checked the unchanged
  placeholders and remaining prompt instructions. Diff evidence:
  `backlog/log/STORY-018/reviewer-diff.log`.
- No prior workflow check log exists. The whole suite is left to the workflow's
  verify step as specified. The project provides no separate lint, type-check,
  or build check target.

Per-criterion test record (numbered in acceptance-criteria order):

1. No test: the level-neutral proof rule and explicit end-to-end exemption are
   prose, verified by reading the role.
2. No test: retaining the mock-evidence rule is a prose change, verified by
   reading the role.
3. No test: naming proving tests or judging recorded reasons is a prompt
   instruction, verified by reading the prompt.
4. No test: removal of the real-system preference and absence of a ranking
   between narrative and unit tests are prose, verified by reading the role.
5. No test: accepting or challenging a recorded no-test reason is a role
   instruction, verified by reading the role.
6. No test: the narrow exception for the per-criterion test record under
   `## Implementation` is prose, verified by reading the prompt.
7. No test: the amended opening permits the test record without naming its
   heading; this is prose, verified by reading the role.
8. No test: the approval and revision rules are prompt prose, verified by
   reading the prompt.
9. No new test: wording placement and unchanged surrounding instructions are
   prose, verified in the diff. Existing `tests.test_requests` passed as a
   compatibility check for prompt rendering; it does not prove the wording.
10. No unit test: file scope is verified from the working-tree diff, rather
    than tested in product code. Only the two specified files and this item
    body change, with required evidence logs saved separately. Whole-suite
    proof remains with the workflow's verify step.

No criteria require new tester narrative tests: these changes are role and
prompt prose. There are no blocked criteria or outstanding findings.

## Tests

No narrative tests added. The story changes only `roles/reviewer.md` and
`prompts/review.md`, which are prose read by an AI reviewer. No system entry
point exposes their wording, and the project instructions say prompt and role
changes get no tests that pin wording. A test asserting phrases in those files
would be brittle and would not prove the reviewer's behaviour.

Criteria left to reading (no automated test, as the implementer recorded): all
ten. Criteria 1-8 are wording in the role or prompt; criterion 9 (placeholders
preserved) is covered for rendering by the existing `tests.test_requests`, which
renders the review prompt with all five placeholders; criterion 10 is a diff
scope check for the reviewer.

Whole suite: `dev-team check` passed (275 tests). Log:
`backlog/log/check/20261009T150114262251.log`.

Run one test on its own: `dev-team check tests.test_requests`.

## Test run

Run by the harness, 2026-10-09 15:06:01 UTC: passed (exit 0); duration 107.883 seconds.

## Review

No findings. The change is sound.

Criteria satisfied. All ten are prose and the implementer recorded "no test" with a reason for each. I accept those reasons: the wording of a role or prompt file is not something a test can usefully pin, and the project instructions say so.

1. `roles/reviewer.md` "Claims without evidence": proven by a test at any level that would fail if broken, unit and narrative named, no end-to-end requirement. Recorded reason accepted.
2. Same bullet keeps the mock rule ("a test that mocks the thing it says it proves; that test is not evidence"). Recorded reason accepted.
3. `prompts/review.md` asks for the proving test (unit or narrative), or the recorded reason and whether it is accepted. Recorded reason accepted.
4. "The strongest evidence runs the real system" is gone from the role, and no level is ranked above another. Recorded reason accepted.
5. The role bullet judges a recorded no-test reason: accept it (counts as proven for approval) or say why a test is needed. "Without a proving test or an accepted recorded reason, it is unproven" keeps the earlier challenge's reading. Recorded reason accepted.
6. `prompts/review.md` makes the per-criterion test record the one exception, and the implementer's account of changes is still not evidence. Recorded reason accepted.
7. The role opening no longer says "should not go looking for it", permits the test record, and does not name `## Implementation`. Recorded reason accepted.
8. The approve rule reads as specified; `revise` otherwise, including an empty diff. Recorded reason accepted.
9. The naming instruction sits in the same paragraph as the list of satisfied criteria. All five placeholders are present and unchanged in the diff. `tests.test_requests`, which renders the prompt, passes in the harness run. Recorded reason accepted for the wording.
10. `git diff main...devteam/STORY-018 --stat` shows only `roles/reviewer.md` and `prompts/review.md` changed. The whole suite passed (275 tests, exit 0): `backlog/log/STORY-018/verify-20261009T150413766253.log`.

Minor and non-blocking: one added line in `prompts/review.md` ("recorded that there is no test, state that recorded reason and whether you accept it.") runs past the 80-column wrap used elsewhere.
