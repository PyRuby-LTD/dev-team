---
id: STORY-021
type: story
title: Publish only the requirements in docs/work-items
parent: EPIC-001
workflow: default
step: publish
---
As a customer reading the repository, I want the published work item in `docs/work-items/<id>.md` to hold only the requirements, so that the story reads as what was asked for and the code is the delivery of it.

## Context

REQUEST-006. Story bodies in the backlog accumulate working notes (analysis, challenge, tests, implementation, review, pull request). Those exist to pass context between agent steps and are of no historical interest. The backlog item stays a single file for agents; only the published copy changes. The copy is written by the `role.record` block in `Runner.invoke` (`devteam/runner.py`).

Only the publisher role has `record = true` (`config/roles.toml`), so only items that reach the publisher step are published: stories, bugs and tasks. Requests follow `workflows/analysis.json`, which has no publisher step, and are never published.

The filter depends on STORY-022. That story makes analysts and the product owner revise Context and Acceptance Criteria in place, so each item carries one plain `## Acceptance Criteria` list and no parallel "tightened", "current" or "original" copy. Items analysed before STORY-022 ships (for example STORY-012 and STORY-013, which keep their criteria under qualified headings) will be published with those qualified sections omitted. That is accepted; existing records are not migrated.

A published bug carries no `## Cause` or similar diagnosis section, since that is a working note. Dropping it is intended: the criteria say what correct behaviour is.

## Acceptance Criteria

1. The published copy `docs/work-items/<id>.md` has, in this order: the front matter unchanged, the preamble (text before the first `##` heading), then the `## Context` and `## Acceptance Criteria` sections in the order they appear in the item, with the text of each as in the item. Nothing else appears. Sections are separated by a single blank line, and the file ends with a single newline.
2. Every other `##` section is omitted along with its content and any `###` subheadings. This includes `## Questions`, `## Feedback`, `## Analysis`, `## Challenge`, `## Created work items`, `## Pull request`, `## Test run`, and any section with an invented heading, such as `## Response to the third challenge`.
3. The kept section names are held in one named constant (an allow-list), not a deny-list, so a new heading is omitted by default.
4. A kept heading is matched exactly, ignoring case and trailing whitespace. A heading that merely starts with or contains a kept name, such as `## Acceptance Criteria (tightened)` or `## Original acceptance criteria`, is omitted, even when an item also has the plain `## Acceptance Criteria`.
5. If an item has more than one section with a kept name, every one is kept, in item order. No de-duplication is attempted.
6. Stories, bugs and tasks that are published are filtered identically. Requests are not published and need no change.
7. Records already on `main` and existing backlog items are not rewritten or migrated.
8. `PathGuard` masking runs on the filtered text. Text that would be masked in an omitted section is neither published nor reported. A masked line in a kept section is reported with its line number in the published copy (front matter lines plus the line within the filtered body).
9. Re-publishing after rework rewrites the copy from the current item body: a section added to the item since the last publication does not appear, and an edit to Context or Acceptance Criteria does.
10. The backlog item itself, the agent protocol, the TUI, question and feedback handling and PR URL parsing are unchanged; the PR URL is still read from the backlog item.

## Analysis

What exists today: `Runner.invoke` in `devteam/runner.py` (the `if role.record:` block) copies the whole item to `docs/work-items/<id>.md`. It masks `record.body` with `PathGuard.mask`, prepends the original front matter, commits it, and reports masked line numbers as `len(front.splitlines()) + n`. There is no section filtering anywhere. The copy is written by every step whose role has `record` set, so each rework rewrites it from the current body (criterion 9 holds once the filter is in place). `devteam/questions.py` already has the `#`/`##` heading regex and section-splitting idioms, which the filter can reuse. The PR URL is read from the backlog item, not the copy, so criterion 10 is unaffected.

What would change: a small filter is applied to `record.body` before masking. It keeps the preamble and the sections whose `##` heading equals an allow-list constant, `("Context", "Acceptance Criteria")`. Masking then runs on the filtered text, and the offset calculation stays correct because it counts from the front matter in the copy.

Assumptions (not questions):
- Heading matching is case-insensitive and ignores trailing whitespace. The census of existing items shows both `Acceptance Criteria` and `Acceptance criteria` in use.
- A section runs from its `##` heading to the next `#` or `##` heading, as in `questions.HEADING`. `###` and deeper subheadings stay with their parent section.
- A line starting `## ` inside a fenced code block is not a heading. Neither this nor a level-one `# ` heading is expected in practice; if the fence case is ambiguous, treating it as a heading is acceptable provided it is consistent.
- The seam and final-newline rule is now part of criterion 1.
- If an item has no `## Context` or no `## Acceptance Criteria`, the copy simply lacks it; nothing is invented.
- Wording in the criteria is checked by reading the published file.

Pointer for the implementer (not a criterion; which tests to write and at what level is the implementer's and tester's call). Existing tests that encode the old whole-body copy and will fail until updated:
- `tests/test_run_evidence.py` `test_the_record_copied_for_publication_matches_the_item...` asserts a `## Test run` section is in the copy.
- `test_a_body_that_trips_nothing_is_copied_unchanged` asserts the copy body equals the backlog body.
- `test_a_tripping_body_is_masked_in_the_copy...` appends text at the end of the body, which falls in the last section (and so is dropped). It must place the tripping text in a kept section or the preamble.
- `tests/test_checkout.py` around line 176 and the `docs/work-items` diff check around line 601 should be re-run.

## Challenge

Sound: a competent engineer could implement criteria 1 to 10 as written, and a reviewer could tell from the published file and the runner's report whether they had. Both earlier findings are resolved. No criterion now prescribes tests. Criterion 1 now fixes item order and holds the blank-line and final-newline rule, so it no longer conflicts with criterion 5.

Evidence: this challenge only read files; no `dev-team check` was run. The earlier heading census remains in `backlog/log/STORY-021/challenge-heading-census.txt` and `backlog/log/STORY-021/challenge-older-item-headings.txt`. The claims about the code still hold. The `role.record` block at `devteam/runner.py:306-316` masks `record.body`, prepends the front matter and reports `len(front.splitlines()) + n`. Criterion 8 therefore needs only the filter applied before `mask`. `questions.HEADING` is at `devteam/questions.py:7`. `record = true` appears only under the publisher (`config/roles.toml:89`). Nothing in `devteam/`, `prompts/` or `roles/` reads `docs/work-items` except where it is written (`RECORDS`, `devteam/runner.py:18`). That supports criterion 10: dropping `## Pull request` from the copy cannot break PR URL parsing.

Residual point, which does not change what gets built: the fenced-code assumption in Analysis leaves the choice to the implementer ("acceptable provided it is consistent"). That is acceptable because no criterion depends on it and the case is not expected in practice.

Cheapest way to be wrong: unchanged. The risk is that items analysed after STORY-022 still use a qualified criteria heading, which this filter would drop. The smallest check is to read the headings of the first item analysed after STORY-022 merges, before it reaches the publisher.

## Response to the challenge

1. Accepted. Former criteria 11 (update old tests) and 12 (journey-level test) are removed; they prescribed tests. The mixed-heading case is covered as behaviour in criterion 4 (a qualified heading is omitted even beside the plain one) and criterion 2 (invented headings). The affected tests remain in Analysis as a pointer only.
2. Accepted. Criterion 1 now says Context and Acceptance Criteria appear in item order, matching criterion 5, and the single-blank-line seam and single final newline rule is part of criterion 1.

Verdict: understood well enough to implement; no customer questions.

## Implementation

Implemented the requirements-only publication filter in `devteam/publication.py` and applied it in `Runner.invoke` before `PathGuard.mask`. `PUBLISHED_SECTIONS` is the single allow-list. The filter preserves the preamble, allowed headings and their contents in item order, retains duplicates and nested subheadings, and normalises blank lines between blocks and the final newline. It uses the existing item-parser convention that a level-one or level-two heading ends a section; heading-like lines inside fences are treated consistently as headings, as permitted by Analysis.

Updated the existing publication assertions to expect requirements only, preserve the original front matter and backlog body, and check masking against published line numbers. Added focused filter unit tests and a publication check that omitted paths produce no copy-mask report. Existing records and other backlog items were not migrated. The protocol, UI, questions, feedback and PR parsing code were not changed.

Acceptance criterion coverage:

1. Unit tests in `tests/test_publication.py` prove body selection, item order, subheading/content preservation, missing sections and newline boundaries. The updated existing publication test checks unchanged front matter and the assembled copy. Formatting and wording are also left to human judgement at review.
2. Unit test `test_omits_every_unknown_section_including_qualified_names` covers the named working sections, an invented heading, diagnosis notes and nested content.
3. No unit test: the named `PUBLISHED_SECTIONS` allow-list is plain code; criterion 2's unit test proves omission by default.
4. Unit tests cover case-insensitive exact names, trailing whitespace and qualified names beside the plain criteria heading.
5. Unit test `test_matches_case_and_trailing_whitespace_and_keeps_duplicates` proves duplicate preservation in item order.
6. No new unit test: all recorded item types share the same unconditional publication block; no type dispatch or request workflow was changed. This is plumbing for review.
7. No new unit test: there is no migration code. The existing `TestRecordsAlreadyCompleted` check was rerun and passes; review can confirm the diff contains no published records or other backlog items.
8. No new unit test for plumbing: masking now receives the filter's result. Existing process-level publication tests verify the retained path's line number in the published copy, and the added publication check verifies omitted paths are neither copied nor reported by publication. Backlog masking continues independently as before.
9. Left to the tester's journey tests: rework and republish an item after adding working notes and editing its requirements. Each invocation already rewrites the copy from the current body through the new filter; no new caching or rework logic was needed.
10. No new unit test: these unrelated paths are unchanged. The updated existing publication test also checks that the backlog body is unchanged. The runner, checkout and run-evidence module checks passed; the PR/rework user journey remains for the tester.

Checks and evidence:

- Direct affected-module tests: `UV_CACHE_DIR=/tmp/devteam-story-021-uv-cache uv run python -m unittest tests.test_publication tests.test_run_evidence tests.test_runner tests.test_checkout` — passed, 64 tests. Evidence: `backlog/log/STORY-021/unit-tests.log`. This includes both the checkout publication test and the existing-record diff test called out in Analysis.
- `UV_CACHE_DIR=/tmp/devteam-story-021-uv-cache uv build` — passed, source distribution and wheel built. Evidence: `backlog/log/STORY-021/build.log`.
- `git diff --check` — passed. Evidence: `backlog/log/STORY-021/diff-check.log` (empty output on success).
- The initial default-cache test invocation failed before running tests because the sandbox cannot write the default uv cache. Reproduced evidence: `backlog/log/STORY-021/default-cache-attempt.log`. Using the writable `/tmp` cache resolved it.
- No separate linter or type-check command is configured in the repository. The full suite was not run, as requested. No workflow check log was supplied; none had run yet.

No outstanding implementation blockers.

## Tests

Journey tests (drive `dev-team run --once` against a real product repo with stubbed agents, then read the published file from git):

- `tests.test_run_evidence.TestPublicationCopy.test_publication_preserves_front_matter_and_only_copies_requirements` covers criteria 1, 2, 4 and 10 (copy holds front matter, preamble, Context and Acceptance Criteria only; backlog body unchanged).
- `tests.test_run_evidence.TestPublicationCopy.test_a_tripping_body_is_masked_in_the_copy_and_the_step_carries_on` and `test_paths_in_omitted_sections_are_not_reported_by_publication` cover criterion 8.
- `tests.test_run_evidence.TestPublicationCopy.test_republishing_after_rework_rewrites_the_copy_from_the_current_requirements` is new and covers criterion 9: reject, rework, republish; the new section is absent and the edited Context and criteria are present.
- `tests.test_checkout` and the `docs/work-items` diff check in `tests.test_run_evidence` cover criterion 7.

Left to unit tests (`tests/test_publication.py`): criteria 3, 5, and the detail of 1, 2 and 4 (ordering, case and whitespace matching, qualified headings, duplicates, subheadings, seams). Criterion 6 is shared plumbing with no per-type dispatch. Wording is left to human judgement at review.

Run one test on its own: `dev-team check tests.test_run_evidence.TestPublicationCopy`.

Whole suite passed (373 tests): `backlog/log/check/20261026T215320936388.log`.

## Review

No findings. The change is sound.

Evidence: harness full suite passed, 373 tests (`backlog/log/STORY-021/verify-20261026T215636725562.log`). The diff touches only `devteam/publication.py`, one import and call in `devteam/runner.py`, and tests. No backlog items or records are rewritten.

Criteria:

1. Met. `requirements()` keeps the preamble and allowed sections, joins them with one blank line and ends with one newline. The front matter is prepended unchanged in `runner.py`. Proven by `tests.test_publication` (order, seams) and `TestPublicationCopy.test_publication_preserves_front_matter_and_only_copies_requirements`, which compares the whole file.
2. Met. Anything not on the allow-list is dropped with its `###` content. Proven by `test_omits_every_unknown_section_including_qualified_names`.
3. Met. `PUBLISHED_SECTIONS` is an allow-list constant. The implementer recorded no separate test, because criterion 2's test shows omission by default. I accept that reason.
4. Met. The heading is matched exactly after `casefold()` and trailing-whitespace strip, so qualified names are omitted. Proven by the qualified-name cases and the case/whitespace test.
5. Met. Duplicates are kept in item order. Proven by `test_matches_case_and_trailing_whitespace_and_keeps_duplicates`.
6. Met. The block runs for every item that reaches the publisher, with no type dispatch. The recorded reason of shared plumbing is accepted.
7. Met. The diff has no migration and no changes to existing records. The `docs/work-items` diff check in `tests.test_run_evidence` and `tests.test_checkout` still pass.
8. Met. `mask` is now called on `requirements(record.body)`. Proven by `test_a_tripping_body_is_masked_in_the_copy_and_the_step_carries_on`, which checks the line number in the copy, and `test_paths_in_omitted_sections_are_not_reported_by_publication`.
9. Met. The copy is rebuilt from the current body on each publication. Proven by `test_republishing_after_rework_rewrites_the_copy_from_the_current_requirements`.
10. Met. Only the publication call changed. The backlog body is asserted unchanged in the publication test, and the PR/rework journey passes.

Residual, not blocking: a `## ` line inside a code fence is treated as a heading. Analysis permits this, provided it is consistent.

## Test run

Run by the harness, 2026-10-26 22:22:27 UTC: passed (exit 0); duration 189.400 seconds.
