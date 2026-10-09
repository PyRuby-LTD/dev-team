---
id: STORY-017
type: story
title: Analyst and challenger focus on what is built, not how it is tested
parent: EPIC-006
workflow: default
step: publish
---
**As a** customer running dev-team
**I want** the analyst and challenger to concentrate on what is to be built and on unambiguous criteria
**So that** the implementer and tester decide how the work is proven, rather than being handed a test plan

## Context

`roles/analyst.md` asks for criteria that can be checked by "running a test",
and `roles/challenger.md` attacks criteria and scope in ways that can drift into
prescribing tests. The request wants these roles to define the need and leave
test design to the implementer and tester. Only `roles/analyst.md`,
`roles/challenger.md` and `prompts/challenge.md` change.

## Analysis

Findings against the repository:

- `roles/analyst.md` lines 9-11 define criteria as statements checkable "by reading a diff or running a test". That is the only test reference in the file.
- `roles/challenger.md` lists five fronts. The third ("Criteria that cannot be checked") says a criterion nobody could fail "by reading a diff or running a test" is an avoided decision. That is the only test reference in the file, and it frames the challenger's test as checkability by tests rather than unambiguity.
- `prompts/challenge.md` already contains no instruction to propose or require tests. Its criterion below is already true and acts as a guard, not a change.
- `devteam/config.py` loads role files as briefs, and `tests/test_requests.py` checks that each brief is non-empty. `tests/test_run_evidence.py` scans the role and prompt files for prohibited evidence instructions. None pins the wording being changed, so the change is prose only, consistent with the request feedback excluding Python changes. Existing tests are not expected to be affected.

What would change: reword the analyst's definition of a criterion around observable behaviour and what is built, with an explicit statement that test selection and level are left to the implementer and tester. Reword the challenger's third front to ask whether a criterion is unambiguous enough to be implemented and verified, and add an explicit statement that the challenger does not prescribe tests. `prompts/challenge.md` is expected to stay unchanged.

Assumptions: renaming the third front is acceptable provided the other four fronts survive unchanged. "Reading a diff" may remain as a notion of checkability, as it names no test.

The item is understood well enough to implement; there are no customer questions.

## Acceptance Criteria

- [ ] **Given** `roles/analyst.md`, **When** read, **Then** it defines acceptance criteria as statements of observable behaviour and what is to be built, rejects criteria too vague to be implemented and verified, no longer uses "running a test" as the measure of a criterion, and states that the analyst does not specify which tests, at what level, should prove them.
- [ ] **Given** `roles/challenger.md`, **When** read, **Then** its test for criteria is whether each is unambiguous enough to be implemented and verified, it no longer uses "running a test" as the measure, and it says explicitly that the challenger does not prescribe which tests to write or at what level.
- [ ] **Given** `roles/challenger.md`, **When** read, **Then** the text of its existing fronts on unevidenced claims, inference presented as the customer's decision, scope without an outcome and the cheapest way to be wrong is unchanged.
- [ ] **Given** `prompts/challenge.md`, **When** read, **Then** it contains no instruction to propose or require tests (true today; it must not gain one).
- [ ] No file other than those three (and this work item) is changed, no Python is changed, and `dev-team check` still passes.

## Challenge

Sound: a competent engineer could implement this as written and a reviewer could tell from the diff of the two role files whether they had. The findings below are corrections and tightenings; none changes what gets built.

Checked against the repository and found to hold: the line references and "only test reference" claims for `roles/analyst.md` and `roles/challenger.md`; that `prompts/challenge.md` has no instruction to propose or require tests; that `prompts/analysis.md` (the analyst's own prompt, not mentioned in the item) has no test reference either, so leaving it out of scope is right. Each criterion traces to the customer's sentences in REQUEST-004 about the analyst and challenger, and the file boundary matches the customer's feedback there.

1. **One claim in the Analysis is false, though its conclusion survives.** The item says nothing in `devteam/` or `tests/` reads the content of the three files. `tests/test_run_evidence.py` (`test_no_prompt_or_brief_tells_an_agent_to_read_or_paste_test_output_in_the_item`) reads every file under `prompts/` and `roles/` and rejects three phrases: "actual output", "only test output you should trust", and a reference to reading `## Test run`. `devteam/config.py` also loads each role file as the brief, and `tests/test_requests.py` asserts each brief is non-empty. None of these pins the wording being changed, so "prose only, existing tests unaffected" stands, but the implementer should know the new wording is scanned for those phrases. Fix: correct the sentence.

2. **Criterion 1 does not require the analyst to keep any bar for criteria.** The story's "I want" asks for unambiguous criteria from both roles, and criterion 2 demands it of the challenger, but criterion 1 only says what the analyst's definition must stop saying and that it mentions observable behaviour. A rewrite that deleted "Criteria that cannot be checked ... are not criteria" outright would pass. `prompts/analysis.md` still asks for "concrete and checkable" criteria, which limits the damage. Fix: have criterion 1 also require that the analyst role still rejects criteria too vague to be implemented and verified.

3. **"Retained" in criterion 3 is looser than the assumption it rests on.** The Analysis says the other four fronts "survive unchanged"; the criterion says "retained", which permits rewording that a reviewer would then have to judge for equivalence. Fix: say the text of those four fronts is unchanged.

4. **Stated assumption worth the customer's eye at the play decision, not a blocker.** The customer wrote that the challenger "should just make sure the ACs are unambiguous ... rather than prescribing what tests should be done". The item reads "just" as contrasting with prescribing tests, and keeps the four other fronts. That is the natural reading and the item declares it as an assumption; the other reading (the challenger does nothing but check ambiguity) would gut the role. Cheapest check if in doubt: one question to the customer.

Not verified: `dev-team check` was not run on the unchanged tree, because the command was not permitted in this session. The baseline for the last criterion is therefore taken on trust.

## Implementation

Addressed Review findings 1 and 2 by deleting `tests/test_role_briefs.py`, the added Python module that violated the file boundary and pinned the role prose word for word. No replacement tests were added. Against the branch's common ancestor with `main`, the resulting product diff changes only `roles/analyst.md` and `roles/challenger.md`; no Python changes remain.

The existing analyst and challenger wording already meets criteria 1 and 2 and is preserved: criteria describe observable behaviour and what is built, must be unambiguous enough to implement and verify, and leave test selection and level to the implementer and tester. The challenger's other four fronts are unchanged. `prompts/challenge.md` already meets criterion 4 and remains unchanged, as Review finding 3 acknowledges.

Checks and evidence:

- Read the latest workflow check, `backlog/log/STORY-017/verify-20261009T113645932344.log`: the prior full suite passed (284 tests, exit 0). This predates the deletion and includes the nine removed tests.
- Direct unit tests (`tests.test_run_evidence.TestStoryFromStartToPublication.test_no_prompt_or_brief_tells_an_agent_to_read_or_paste_test_output_in_the_item` and `tests.test_requests.Requests.test_workflow_roles_prompts_and_hub_transitions`): passed, 2 tests. Evidence: `backlog/log/STORY-017/revision-unit-tests.log`.
- `dev-team check tests.test_run_evidence.TestStoryFromStartToPublication.test_no_prompt_or_brief_tells_an_agent_to_read_or_paste_test_output_in_the_item`: passed, 1 test. Harness evidence: `backlog/log/check/20261009T115829038484.log`.
- `git diff --check`: passed. Evidence: `backlog/log/STORY-017/revision-diff-check.log`.
- Product diff scope against the branch's common ancestor with `main`: only the two role files remain changed. Evidence: `backlog/log/STORY-017/revision-scope-check.log`.

No current checks failed. The full suite was not rerun here; it is run after the tester's step as instructed. The earlier Implementation's sandbox-stalled attempts are historical, not current results.

Status: implemented. All review findings are addressed; no blockers remain.

## Tests

No new tests were added. The item's last criterion and Context forbid any Python change, and the review rejected `tests/test_role_briefs.py` for breaking that boundary and for pinning prose word for word. Criteria 1 to 4 describe the wording of role and prompt files, not behaviour of the running system, so a regression test could only compare text. If the customer wants the wording pinned, that is a change to the criteria for them to make.

- Criteria 1 to 4 (wording of `roles/analyst.md`, `roles/challenger.md`, `prompts/challenge.md`): verified by reading the diff, as recorded in the Review. The harness already exercises these files at run time: `tests.test_requests.Requests.test_workflow_roles_prompts_and_hub_transitions` loads every role brief and prompt and requires each to be non-empty, and `tests.test_run_evidence.TestStoryFromStartToPublication.test_no_prompt_or_brief_tells_an_agent_to_read_or_paste_test_output_in_the_item` scans them for prohibited phrases.
- Criterion 5: the file-boundary part is a property of the diff. The `dev-team check` part is covered by the full suite, which passed (275 tests). Harness evidence: `backlog/log/check/20261009T115932542904.log`.

Run one test on its own, for example:
`dev-team check tests.test_run_evidence.TestStoryFromStartToPublication.test_no_prompt_or_brief_tells_an_agent_to_read_or_paste_test_output_in_the_item`

## Test run

Run by the harness, 2026-10-09 12:07:42 UTC: passed (exit 0); duration 221.805 seconds.

## Review

Verdict: approve. The earlier finding (an added Python test file) is fixed; nothing blocks.

Findings: none blocking. One observation, not a defect: no test pins the new wording, so a later edit could reintroduce "running a test" unnoticed. The item forbids Python changes, so that is the customer's call.

Criteria satisfied, with evidence:

- Criterion 1 (analyst): `roles/analyst.md` now says "concrete statements of observable behaviour and what is to be built", "Criteria too vague to be implemented and verified are not criteria", and that the analyst "does not specify which tests, or at what level, should prove them". "running a test" is gone. Seen in `git diff main...devteam/STORY-017`.
- Criterion 2 (challenger): the third front is "Ambiguous criteria" and requires each criterion to be "unambiguous enough to be implemented and verified". A new paragraph says the challenger does not prescribe which tests to write or at what level. "running a test" is gone. Seen in the diff.
- Criterion 3: the diff touches only the third bullet and adds one paragraph after the list; the other four fronts are textually unchanged. Seen in the diff.
- Criterion 4: `prompts/challenge.md` is not in the diff.
- Criterion 5: `git diff main...devteam/STORY-017 --name-only` lists only `roles/analyst.md` and `roles/challenger.md`; no Python changed. The harness full suite passed (275 tests, OK, exit 0): `backlog/log/STORY-017/verify-20261009T120400734189.log`.
