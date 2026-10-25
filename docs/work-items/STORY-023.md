---
id: STORY-023
type: story
title: Detect a merged pull request automatically
parent: EPIC-008
workflow: default
step: publish
---
As a customer, I want an item waiting at `pull-request` to move on by itself once its pull request is merged on GitHub, so that I do not have to come back to the TUI to tell it what I have already done.

## Context

Today `pull-request` is a human-owned step in `workflows/default.json` with the transitions `merged` and `rejected`; the customer merges on GitHub and then chooses `merged` in the TUI. The PR URL is recorded under `## Pull request` in the item body by the publisher, and `runner.rejected` in `devteam/runner.py` already parses it with `PR_URL` and calls `gh`.

Decisions:

- The runner polls the state of the PR for each item at `pull-request`, for example with `gh pr view <url> --json state`, at a modest interval (about a minute), not on every dispatch pass.
- Only a merged PR is acted on: the runner applies `merged`, after which the existing `merged` harness action runs as today. A PR that is closed without merging, or has changes requested, is left for the customer to decide.
- The customer can still choose `merged` or `rejected` by hand at any time.
- A failed lookup (no URL, `gh` missing or unauthenticated, network error) must not mark the item failed or stop the runner; it is reported, without repeating the same message every poll.

This is independent of the other stories in the epic.

## Analysis

What exists today:

- `pull-request` in `workflows/default.json` is `owner: human`, so `Runner.pending()` (`devteam/runner.py`) never selects it; nothing watches GitHub. `merged` is a harness step (`HARNESS_ACTIONS`) that fast-forwards the base branch using the shared checkout, then applies `completed`.
- PR URL lookup exists only inline in `rejected()`: it finds the `## Pull request` section and takes the last `PR_URL` match, raising `StepFailed` if there is none. It would need to be extracted so both paths share it.
- `gh` is called with `subprocess.run` and a timeout (`pr_comments`, `GH_TIMEOUT`); the test stub `tests/stubs/gh` only imitates `gh api` and would need to answer `gh pr view` too.
- `Runner.run` loops `dispatch()` every `interval` seconds (2s by default, `REFRESH_SECONDS` in the TUI). `note_waiting` already gives "report once per distinct message" behaviour. Both the CLI (`dev-team run`) and the TUI drive `Runner.run`, so a poll inside the runner covers both.
- `Repository.transition(id, "merged")` raises `InvalidRecord` if the item is no longer at `pull-request`, which is what happens when the customer chooses by hand between the poll and the transition.

What would change:

- The runner gains a throttled check of every non-failed item at `pull-request`, separate from the dispatch of agent/check/harness steps. On a merged PR it applies `merged`, after which the existing `merged` harness step runs unchanged.
- Remembering when each item was last checked and which problem was last reported lives in the runner (in memory, like `_failed` and `_waiting`).

Assumptions (not questions):

- "Merged" means GitHub reports the PR state as `MERGED`. `OPEN` and `CLOSED` (unmerged) are left alone silently.
- The check applies to the PR URL in the item body; if several are recorded, the last one counts, as for `rejected`.
- The interval is about 60 seconds per item and a first check happens soon after the item arrives at `pull-request` (or the runner starts), not a full interval later.
- Lookups run off the runner loop thread (for example a worker thread or subprocess started without waiting), so a slow or hung `gh` never delays dispatch of other items. The loop collects finished lookups on each pass.
- The poll does not use the shared checkout, so it never waits on another item.
- `run --once` does not poll at all. It is for draining agent/check/harness work and must stay hermetic and finite; existing tests that run `--once` to `pull-request` with a real GitHub URL in the body therefore never call `gh pr view`. A merge is detected only by a long-running runner (`dev-team run` without `--once`, or the TUI).
- A lookup failure is not recorded in `failed` and the item is checked again at the next interval. The same failure text is reported once; a different failure, or a failure after a success, is reported again.

## Acceptance criteria

1. With the runner running and an item at `pull-request` whose `## Pull request` section holds a PR URL, once GitHub reports that PR as merged the item moves to `merged` without any action in the TUI, the `merged` step then runs and the item reaches `done` as it does after a manual `merged`. The runner reports the transition.
2. Both `dev-team run` and the TUI do this, since both run the runner.
3. An item whose PR is open, or closed without being merged, stays at `pull-request` and nothing is reported about it. Review states such as changes requested do not move it.
4. At most one lookup per item is started in any 60 seconds, measured from the start of the previous lookup, and this holds whether that lookup succeeded or failed (a failure does not restart or shorten the clock). The first lookup for an item happens on the first runner pass that sees it at `pull-request`, including the first pass after the runner starts. Several waiting items are each checked on that cadence, and a lookup still outstanding for an item is not duplicated.
5. The customer can still choose `merged` or `rejected` in the TUI at any time. If they do so while a check is in progress, the item ends in the step they chose, nothing is marked failed, and no error is reported because of the lost race.
6. Each of these leaves the item at `pull-request`, not in the failed list, with the runner still dispatching other items, and reports the problem: no PR URL in the item, `gh` not installed, `gh` not authenticated, network or timeout error, unparseable `gh` output. The same message is not repeated on later polls while the problem persists; once a poll succeeds, or the message changes, reporting resumes. When the problem clears and the PR is merged, the item moves on.
7. Items at other steps are never queried.
8. The existing behaviour of `rejected`, `merged`, and the other steps is unchanged, and the full test suite passes.
9. While a lookup is outstanding (including one that hangs until `GH_TIMEOUT`), other items' agent, check and harness steps continue to be dispatched within the normal runner interval.
10. `dev-team run --once` makes no `gh pr view` lookups and still returns as it does today; an item left at `pull-request` stays there.

## Notes for implementation

- `workflows/default.json` should not need to change; a custom workflow without a `pull-request` step simply has nothing to poll. Decide how the poll finds "items at pull-request" (by step name is the simplest, and matches the story's wording).

## Challenge

Sound. A competent engineer can build this as written and a reviewer can tell whether they have. The three earlier findings are settled: off-thread lookups are now AC9, `--once` not polling is AC10, and AC4 gives concrete bounds. I checked the claims about the code again against the repository and they hold. `PR_URL` and the inline lookup in `rejected()` are at `devteam/runner.py:20` and `:70-81`, and `GH_TIMEOUT = 60` is at `:19`. `note_waiting` reports only when the message changes (`:238-243`) and `pending()` skips human steps (`:245-253`). The once-mode exit is at `:466-467`. Both `dev-team run` (`devteam/cli.py:57`) and the TUI (`devteam/tui.py:639`) drive `Runner.run`. The TUI's manual choice goes through `Repository.transition` (`devteam/tui.py:574`), which checks the current step under the backlog lock and raises `InvalidRecord` for a transition that step lacks (`devteam/backlog.py:284-320`). That makes AC5's lost race detectable and safe. The stub `tests/stubs/gh` only handles `gh api`, as the item says. Every criterion traces back to the story or to the epic outcome "A merged pull request is detected automatically".

Minor points. Neither changes what gets built.

1. **AC4 and AC5 run together on one line** ("...is not duplicated.5. The customer can..."). In Markdown this makes AC5 part of AC4, and the list then jumps from 4 to 6. Fix: start AC5 on its own line.
2. **Finding the step by name is unguarded for custom workflows.** The notes suggest finding "items at pull-request" by step name. A custom workflow could have a step called `pull-request` with no `merged` transition. There, every merged PR would make `transition(id, "merged")` raise `InvalidRecord`, and by AC5's wording that error could be swallowed silently. Fix, if the analyst wants one: poll only steps that are human-owned and have a `merged` transition, or say that this case is reported like an AC6 problem. The default workflow is not affected (`workflows/default.json:15`).

Riskiest assumption: AC9, that a lookup can run off the loop thread without disturbing dispatch. The quickest way to find out it is wrong is to make the `gh` stub hang on `pr view` while another item has a harness step waiting. If that step is held up, AC9 is not met.

## Implementation

Implemented automatic merge detection in the shared runner. Long-running runners start daemon-thread `gh pr view --json state` lookups immediately for eligible items at `pull-request`, then at most once per 60 seconds per item, measured from lookup start. Outstanding lookups are not duplicated. Only `MERGED` applies the existing `merged` transition and reports it; the existing harness action then completes the item.

Extracted the existing last-URL-in-section parsing for reuse by polling and rejection. Lookup errors are retried without entering the failed list, with reporting suppressed until the message changes or a lookup succeeds. Completed results are checked against the current record under the backlog mutation lock, so manual decisions supersede stale successes and errors. Polling never claims the checkout and is excluded from `run --once`.

Addressed the Challenge notes: restored AC5's separate numbered line, and limited polling to human-owned `pull-request` steps with a `merged` transition. Extended the offline gh stub with state responses and controllable failures/delays. No workflow changes were needed.

Acceptance coverage:

| Criterion | Test decision and evidence |
| --- | --- |
| AC1 | Unit/component tests: `tests.test_pr_polling` proves merged detection and reporting; `tests.test_merged.Merged.test_detected_merge_uses_the_existing_harness_to_reach_done` uses local Git repositories to prove the transition reaches `done` and fast-forwards the base. The customer goal through a running CLI/TUI and GitHub is left to the tester's journey tests. |
| AC2 | No additional unit test: both entry points already call the shared `Runner.run`; this is unchanged plumbing. CLI/TUI customer journeys are left to the tester. |
| AC3 | Unit test: `test_first_pass_last_url_and_silent_unmerged_states` proves OPEN and CLOSED stay put silently, including a changes-requested review decision. |
| AC4 | Unit tests: `test_each_item_has_a_start_based_clock_on_success_and_failure` proves immediate checks, independent item clocks, the 60-second boundary and unchanged cadence after failures; `test_outstanding_lookup_is_not_duplicated_even_after_interval` proves outstanding work is not duplicated. |
| AC5 | Unit test: `test_manual_decisions_win_over_in_progress_results_and_errors` covers both manual transitions and stale success/error results, with no failure or error report. Existing manual PR decision tests also pass. Manual TUI controls are unchanged plumbing; their presentation is left to human judgement. |
| AC6 | Unit tests: `test_bad_output_missing_url_executable_network_authentication_and_timeout_are_recoverable` covers each listed failure and deduplicated reporting; `test_failures_are_reported_once_until_success_or_changed_message` proves recovery, changed-message reporting, reset after success and eventual merging. AC9's test proves dispatch continues during a real subprocess timeout. |
| AC7 | Unit test: `test_other_steps_failed_items_and_unsupported_custom_steps_are_not_queried` excludes other steps, failed items and unsupported custom decision steps. |
| AC8 | Existing runner, rejection/feedback, merge, dispatch, checkout and manual PR decision tests pass. The full suite is deliberately left to the later workflow run, as instructed; it was not run or claimed to pass here. |
| AC9 | Unit/component test: `tests.test_dispatch.Dispatch.test_hung_pr_process_does_not_delay_agent_check_or_harness_dispatch` runs a real offline gh process until its timeout while other agent, check and merge harness work reaches `done`. |
| AC10 | Unit test: `test_once_never_queries_github_and_returns_at_pull_request` proves no lookup and a finite return. Existing once-mode tests in the runner and CLI modules also pass. |

Checks and evidence:

- Direct unit tests: `python -m unittest tests.test_pr_polling tests.test_runner tests.test_pr_feedback tests.test_merged tests.test_dispatch` — passed, 54 tests. Output: `backlog/log/STORY-023/unit-tests.log`.
- Direct regression tests (including a rerun of polling tests after simplifying the custom-workflow fixture): `python -m unittest tests.test_pr_polling tests.test_checkout tests.test_pr_decision tests.test_merged_cli` — passed, 40 tests. Output: `backlog/log/STORY-023/regression-tests.log`.
- `dev-team check tests.test_pr_polling` — passed, 8 tests. Harness-saved output: `backlog/log/check/20261025T174214162914.log`.
- `uv build --out-dir /tmp/STORY-023-dist` — passed; source distribution and wheel built. Output: `backlog/log/STORY-023/build.log`.
- `git diff --check` — passed. Output: `backlog/log/STORY-023/diff-check.log`. The separate backlog item diff also passed: `backlog/log/STORY-023/item-diff-check.log`.
- No separate lint or type-check commands are configured in this repository. No prior workflow check log was supplied. No check failures or blocked criteria remain. Report wording and TUI presentation are left to human judgement at review.

## Tests

Journey test in `tests/test_merged_detection_cli.py` starts the real, long-running `dev-team run` against a product repository with a remote, and the offline `tests/stubs/gh` stand-in answering `gh pr view` from `tests/fixtures/gh/state.json` style fixtures written per test.

- `test_item_reaches_done_once_its_pull_request_is_merged_on_github`: an item at `pull-request` with a PR URL in its body reaches `done` with no manual action, and the checkout is back on `main` (criteria 1 and 2 in part: the CLI side; the TUI shares `Runner.run`).
- `test_item_stays_at_pull_request_while_the_pull_request_is_not_merged`: with the PR open the item stays put and the runner did look it up (criterion 3 in part).

`tests/fixtures/gh/state.json` was added for the stub's `pr view` answer.

Left to unit tests (`tests/test_pr_polling.py`, `tests/test_dispatch.py`, `tests/test_merged.py`): criteria 3 (closed and changes-requested), 4 (60 second cadence), 5 (manual-decision race), 6 (failure modes and deduplicated reporting), 7, 9 (hung lookup does not delay dispatch) and 10 (`--once` makes no lookups). Criterion 8 is covered by the whole suite passing. Left to human judgement as presentation: the wording of the runner's report and TUI display (criterion 1 report text, criterion 2 TUI).

Whole suite: passed (310 tests), log `backlog/log/check/20261025T174538486207.log`.

Run one on its own: `dev-team check tests.test_merged_detection_cli`, or a single test as `dev-team check tests.test_merged_detection_cli.MergedPullRequestDetectedFromTheCommandLine.test_item_reaches_done_once_its_pull_request_is_merged_on_github`.

## Review

No blocking findings. The full suite passed (310 tests): `backlog/log/STORY-023/verify-20261025T174806897915.log`.

Minor, not blocking:

1. `Runner.poll_pull_requests` (`devteam/runner.py`) calls `self.repository.scan()` in its second loop outside any try. If a scan raised, it would propagate out of `Runner.run`. `dispatch` scans in the same way, so this is not a new class of risk.
2. A lookup result is discarded when the record has changed at all, not only when it has left `pull-request`. The next poll re-checks after 60 seconds, so the merge is delayed by up to a minute. This is safe and rare.

Criteria:

1. Met. `poll_pull_requests` applies `merged` on `MERGED` and reports the transition. The existing harness step then runs. Proven by `tests.test_pr_polling`, `tests.test_merged.Merged.test_detected_merge_uses_the_existing_harness_to_reach_done` and the journey test `test_item_reaches_done_once_its_pull_request_is_merged_on_github`.
2. Met. The poll lives in `Runner.run`, which both the CLI and the TUI drive. The CLI journey test covers it. The recorded reason for no TUI test (shared plumbing) is accepted.
3. Met. OPEN and CLOSED are ignored silently. Proven by `test_first_pass_last_url_and_silent_unmerged_states` and the journey test `test_item_stays_at_pull_request_while_the_pull_request_is_not_merged`.
4. Met. `_pr_started` records the lookup start, and `_pr_lookups` prevents duplicates. Proven by `test_each_item_has_a_start_based_clock_on_success_and_failure` and `test_outstanding_lookup_is_not_duplicated_even_after_interval`.
5. Met. The result is checked against the current record under the backlog `mutation` lock, so a stale success or error is dropped without being reported. Proven by `test_manual_decisions_win_over_in_progress_results_and_errors`.
6. Met. Failures are retried, never added to `failed`, and reported only when the message changes. A success clears the stored problem. Proven by `test_bad_output_missing_url_executable_network_authentication_and_timeout_are_recoverable` and `test_failures_are_reported_once_until_success_or_changed_message`.
7. Met. The poll filters on step name, not failed, human-owned, and having a `merged` transition. Proven by `test_other_steps_failed_items_and_unsupported_custom_steps_are_not_queried`.
8. Met. `rejected` now shares the extracted `pull_request` helper with unchanged behaviour. The whole suite passed.
9. Met. Lookups run in daemon threads. Proven by `tests.test_dispatch.Dispatch.test_hung_pr_process_does_not_delay_agent_check_or_harness_dispatch`.
10. Met. The poll is guarded by `if not once`. Proven by `test_once_never_queries_github_and_returns_at_pull_request`.

## Test run

Run by the harness, 2026-10-25 17:50:23 UTC: passed (exit 0); duration 136.168 seconds.
