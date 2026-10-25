---
id: STORY-027
type: story
title: Replace accept-without-PR with abandon
parent: EPIC-008
workflow: default
step: publish
---
As a customer, I want to abandon a story I have decided not to merge, instead of accepting it without a pull request, so that `done` always means the work reached the base branch and an abandoned story is recorded as such.

## Context

At the `accept` step in `workflows/default.json`, the `accept` transition goes straight to `done` without a pull request. That leaves the `devteam/<id>` branch unmerged locally with no workflow route to get it into the base branch, while the item reads as finished. The README's workflow table describes it (the TUI builds its transition list from the workflow and has no hard-coded mention). No harness code refers to the transition by name.

Decisions:

- The `accept` transition is removed. The step keeps `pr` and `revise`.
- A new `abandon` transition is available at the `accept` and `pull-request` steps. It leads to a new terminal step, `abandoned`, separate from `done`. At `pull-request`, closing the PR on GitHub stays the customer's job, as merging does; the harness does not close it.
- When the checkout is on the abandoned item's branch, it is returned to the item's recorded base branch before the item reaches `abandoned`, so the next story starts from the base. This uses the checkout, so it is a harness action with the same dirty-checkout rules as `merged`. The local branch is kept, not deleted, so the work can be recovered by hand.
- Items already at `done` are not migrated.
- The step name `accept` no longer describes a choice that ends the item. Analysis may propose renaming it (for example to `acceptance`). Any rename must keep existing items valid or migrate them.

With this in place, `done` is reached only through `merged`, which the dependency story in this epic relies on.

## Analysis

What exists today:

- `workflows/default.json` has `accept` (human) with `pr`, `accept` (to `done`) and `revise`, and `pull-request` (human) with `merged` and `rejected`. `done` is a terminal step (no transitions).
- A harness step is declared as `"owner": "harness:<action>"`. `devteam/workflow.py` requires the action to be in `HARNESS_ACTIONS` and requires the step to have exactly one transition, `completed`. `devteam/runner.py` maps actions in its own `HARNESS_ACTIONS` dict. `merged` is the only harness action that uses the checkout: `uses_checkout()` tests `step.action == "merged"`, so the runner holds the checkout lock for it, and the action refuses a dirty checkout (`git.clean`) with `StepFailed`, leaving the item in place until retried.
- `take_checkout` treats a holder on a `devteam/*` branch as finished once its step is terminal, then switches to that branch's recorded base (`branch.<name>.base`) before creating the next branch. So today an abandoned item at a terminal step would rely on the next story to move the checkout; it would not be returned at the moment of abandoning, and a dirty checkout would only surface as a wait for the next story.
- No harness code names the `accept` transition. The TUI skips the feedback-note prompt only when the target step's action is `merged` (`devteam/tui.py:552`); a transition leading to any other harness step would currently prompt for a note.
- Hard-coded references that will break or go stale: `README.md` (workflow table, and the `accept`/`merged` prose near line 195), `tests/test_workflow.py:54`, `tests/test_pr_decision.py` (lines 79, 120-122, 163-165), `tests/test_checkout.py:21-22` (a local workflow fixture, which may stay as it is). `tests/test_run_evidence.py:282` only asserts that an item is at the `accept` step, which stays, so it needs no change. `prompts/review.md` mentions "accepted without" a PR in the sense of tests, not the transition; confirm no change is needed there.

What would change:

- Because a harness step may have only `completed`, `abandon` cannot lead straight to a terminal `abandoned` and also return the checkout. Add an intermediate harness step (for example `abandoning`, owner `harness:abandon`, transition `completed` to `abandoned`), mirroring `merged` to `done`. `accept` and `pull-request` each gain `abandon` leading to that harness step. `abandoned` is a terminal human-owned step like `done`.
- New harness action `abandon` in `devteam/workflow.py` and `devteam/runner.py`. It uses the checkout (`uses_checkout` extended). If the checkout is on `devteam/<id>`, it requires a clean checkout and a recorded base, then switches to the base. If the checkout is on some other branch it changes nothing and completes. It never deletes the branch and does not fetch or fast-forward the base (unlike `merged`).
- Remove `accept` from the `accept` step's transitions; keep `pr` and `revise`.
- TUI: the customer answered question 1: abandon moves without asking for a note. Today only a transition whose target step has action `merged` skips the note prompt (`devteam/tui.py:552`); any other harness target offers the optional note. So that check must be extended to also skip it for a transition into the `abandon` harness step. An item at `abandoned` shows as finished.
- README: update the workflow table, add `abandoning` and `abandoned` rows, and describe abandon in the prose.

Assumptions I am comfortable stating:

- Step naming: the harness step is named `abandoning` and the terminal step `abandoned`; the harness action is `abandon`.
- The `accept` step is not renamed. Renaming would touch every item currently sitting at `accept` (front matter `step: accept`) and the tests above, for no behavioural gain in this story. Existing items at `done` are untouched and not migrated.
- If the checkout is on a different branch (another item's, or the base), abandoning does not move it. A branch with no recorded base fails the step with a message, as `merged` does.
- A failure (dirty checkout, no recorded base, no git repository) leaves the item at the abandoning step, holding the checkout, retryable the same way as `merged`.
- Abandoned items, once at `abandoned`, no longer hold the checkout, so other code-changing items can proceed. The pull request is neither closed nor changed by the harness.

## Acceptance criteria

1. In the default workflow, the `accept` step offers exactly `pr`, `revise` and `abandon`; there is no `accept` transition, and trying it is rejected as an unknown transition.
2. In the default workflow, the `pull-request` step offers `merged`, `rejected` and `abandon`.
3. `abandon` at either step moves the item to a harness-owned step, and from there, once the harness has done its work, to a new terminal step `abandoned`. `abandoned` is distinct from `done`, and `done` remains reachable only through `merged`.
4. Abandoning an item whose checkout is on `devteam/<id>` with a clean working tree leaves the checkout on the item's recorded base branch and the item at `abandoned`. The local `devteam/<id>` branch still exists with its commits afterwards.
5. Abandoning with uncommitted or untracked changes in the checkout on `devteam/<id>` fails: the branch is not switched, the item stays at the abandoning step, the failure is reported with the branch name, and after the checkout is cleaned a retry completes it. Other code-changing items wait while it holds the checkout.
6. Abandoning when the checkout is on some other branch (another item's branch, or the base) leaves that branch checked out and still reaches `abandoned`, whether or not `devteam/<id>` has a recorded base. The clean-tree and recorded-base checks apply only when the checkout is on `devteam/<id>`.
7. Abandoning an item while the checkout is on `devteam/<id>`, where that branch has no recorded base, fails with a message naming the branch, and does not switch branches. (This applies only when the checkout is on `devteam/<id>`; criterion 6 covers every other case.)
8. Abandoning does not fetch, merge, push, or touch the pull request, and does not delete any branch.
9. Once an item is at `abandoned`, it no longer holds the checkout. If the checkout was on `devteam/<id>` when it was abandoned, the next code-changing item starts its branch from the abandoned item's base. If the checkout was elsewhere, abandoning does not move it and the next item starts from wherever the checkout then is.
10. In the TUI, `abandon` is listed as a choice at `accept` and `pull-request`; choosing it moves the item straight on without asking for a feedback note (the customer's answer to question 1); and an item at `abandoned` is displayed as finished with no action for the customer.
11. Items already at `done` and items currently at `accept` or `pull-request` remain valid without migration.
12. `README.md` shows the new transitions and the `abandoning` and `abandoned` steps in the workflow table, describes abandoning in the prose (including that closing the PR is the customer's job), and no longer mentions accepting without a pull request.
13. Existing tests that assert the old `accept` transition are updated to the new behaviour.

## Questions

1. When you abandon a story, do you want the option to leave a note saying why (optional, as when rejecting a PR), or should abandoning move the item without asking?

   **Answer:** Move without asking

## Challenge

Verdict: sound. A competent engineer could build this as written, and a reviewer could tell whether they had. The earlier challenge's findings have been dealt with: the note question was asked and answered (question 1), criteria 7 and 9 are now limited to the case where the checkout is on `devteam/<id>`, and the Context and Analysis corrections are in.

Checked against the repository:

- `workflows/default.json` matches the Analysis. The harness-step rule (`devteam/workflow.py:79-89`, exactly `completed`) means `abandon` needs an intermediate harness step, as proposed.
- Harness actions do not go through `take_checkout` (`devteam/runner.py:437`). So an `abandon` action that does nothing when the checkout is on another branch meets criterion 6 without fighting the runner. Adding the action to `uses_checkout` (`devteam/runner.py:243`) serialises it through `checkout_user`, as criteria 5 and 9 need.
- `merged` (`devteam/runner.py:54-67`) checks the base and a clean tree, and reports the current branch. That is the pattern criteria 5 and 7 describe.
- TUI: terminal steps already show as "finished" (`devteam/tui.py:67`). The only change needed is the note-skip check at `devteam/tui.py:552`, as stated. The target owner for a harness step is labelled `harness`, so the existing tuple does not already cover it.
- The hard-coded references listed (`README.md:146`, `README.md:195-212`, `tests/test_workflow.py:54`, `tests/test_pr_decision.py:79,120-122,163-165`) are the full set. `prompts/review.md:24` ("accepted without one") is about untested criteria, not the transition, so it needs no change. No backlog item sits at `accept` or `pull-request` today, so criterion 11 carries no migration risk.

Observation that does not need rework: STORY-026 (at `ready`) changes when the checkout is held, and adds try-outs that may leave a dirty tree on release. Whichever of the two stories lands second must add `abandoning` to STORY-026's list of checkout steps. It must also decide whether a dirty tree on the item's own branch after a try-out makes `abandoning` fail, as criterion 5 says, or wait. The implementer of the later story should reconcile them, and no customer decision is needed now.

Cheapest way to be wrong: the riskiest assumption is that a failed `abandoning` step keeps other code-changing items waiting (criterion 5). That holds only because the item's branch stays checked out at a non-terminal step, so `take_checkout` raises `Waiting` (`devteam/runner.py:295`). One test with a dirty tree at `abandoning`, followed by queuing a second story, settles it.

## Implementation

Implemented the default workflow's `abandon` decision at `accept` and `pull-request`, through `abandoning` (`harness:abandon`) to terminal `abandoned`. Removed the old `accept` transition. The harness serialises abandonment with checkout work, switches only the item's own clean branch to its recorded base, and retains the branch and commits. Dirty trees and missing bases fail without transitioning; retry uses the existing runner mechanism. Other checkouts are untouched. The TUI skips the feedback note for abandon. Updated the README table and prose, including customer responsibility for closing a PR. Kept the `accept` step name and existing terminal items unchanged.

Acceptance coverage:

1. Unit tests: `tests.test_workflow.WorkflowDefinition.test_pr_decision_gates_completion_after_publish` checks the exact transitions; `tests.test_abandon.Abandon.test_both_customer_steps_abandon_and_only_merged_reaches_done` checks rejection of `accept`. Updated the existing CLI regression too.
2. Unit test: the same workflow test checks the exact `pull-request` transitions.
3. Unit test: `test_both_customer_steps_abandon_and_only_merged_reaches_done` exercises both starting steps through the real repository and harness, checks terminal `abandoned`, and checks `merged` is the sole incoming route to `done`.
4. Unit test with real Git: `test_clean_checkout_returns_to_base_and_next_item_starts_there` checks base checkout and preserved story tip; the helper also checks the base tip is unchanged.
5. Unit test with real collaborators: `test_dirty_tracked_and_untracked_fail_hold_checkout_and_retry` checks tracked and untracked changes, reported branch, unchanged step/branch, a queued implementer's wait, and successful retry. `test_abandon_is_serialised_with_other_checkout_work` checks checkout contention.
6. Unit test with real Git: `test_other_checkout_is_untouched_even_dirty_and_without_recorded_base` covers the base, an unrelated branch and another item's branch, with and without the abandoned branch's base configuration.
7. Unit test with real Git: `test_missing_base_fails_on_item_branch_without_switching` checks failure text, branch and step. `test_no_checkout_fails_without_finishing` also covers missing repository access.
8. No separate unit test for the absence of network/PR/delete plumbing: the action only reads local branch/base/status and switches locally. Real-Git tests run with an unusable remote and check the abandoned branch's commit and the unchanged base commit. No PR collaborator is called by this action.
9. Unit tests: `test_clean_checkout_returns_to_base_and_next_item_starts_there` proves checkout release and the next branch's base/tip. `test_other_checkout_is_untouched_even_dirty_and_without_recorded_base` proves a next item starts on the current base/unrelated branch or resumes its own branch. Existing checkout-holder rules remain in force for other unfinished items.
10. Left to the tester's journey tests: selecting abandon at either customer step moves without a note; this is a user completing a decision through the running TUI. No unit test for the direct note-skip condition or workflow-driven menu plumbing. Finished labels, action presentation and wording are left to human judgement at review; terminal-state behavior is already covered under criterion 3.
11. Unit test: `test_existing_done_accept_and_pull_request_items_remain_valid` checks all three existing states without migration. The existing repository-backlog validation regression also remains in the focused run.
12. No automated test: README prose and table changes are presentation, left to human judgement at review.
13. Updated existing assertions in `tests/test_workflow.py` and `tests/test_pr_decision.py`, replacing direct acceptance with rejection and retaining the PR path. The isolated custom workflow fixture in `tests/test_checkout.py` stays unchanged, as specified in Analysis.

Checks and evidence:

- No prior workflow check log was supplied; the latest status was “No workflow check has run yet.”
- Initial direct run: `.venv/bin/python -m unittest tests.test_abandon tests.test_workflow tests.test_pr_decision` — 31 tests, two errors in the new test fixture's follow-on checkout setup (an unrelated `devteam/*` branch without a recorded base). Corrected the fixture to exercise a normal unrelated branch and the next item's own branch; retained the output at `backlog/log/STORY-027/unit-initial.log`.
- Focused direct run: `.venv/bin/python -m unittest tests.test_abandon tests.test_workflow tests.test_pr_decision tests.test_runner tests.test_merged tests.test_checkout tests.test_dispatch tests.test_tui` — passed, 113 tests in 58.230 seconds; output at `backlog/log/STORY-027/unit.log`. This reruns all tests from the initial failed run. Textual emitted slow-task diagnostics; there were no test failures.
- `UV_CACHE_DIR=/tmp/STORY-027-uv-cache uv build --out-dir /tmp/STORY-027-dist` — passed, source distribution and wheel built. Evidence: `backlog/log/STORY-027/build.log`.
- `git diff --check` — passed. Evidence: `backlog/log/STORY-027/diff-check.log`.
- No lint or type-check command is configured. The full regression suite is reserved for the later workflow check.

## Tests

- Journey: `tests.test_abandon.AbandonThroughTheScreen.test_customer_abandons_at_either_step_without_a_note_and_the_branch_is_kept` drives the TUI over the real default workflow and a real Git checkout. At both `accept` and `pull-request` it checks `abandon` is offered (and `accept` is not at the first), choosing it moves the item on with no note prompt or feedback entry, the harness then completes it to `abandoned`, the checkout returns to `main`, and the `devteam/<id>` branch keeps its commit. Covers criteria 2, 3, 4 and 10 (the choice and no-note parts).
- Left to unit tests: criteria 1, 5, 6, 7, 8, 9, 11, 13 (in `tests/test_abandon.py`, `tests/test_workflow.py`, `tests/test_pr_decision.py`).
- Left to human judgement as presentation: criterion 12 (README) and the finished display of `abandoned` in criterion 10.
- Run one test: `dev-team check tests.test_abandon.AbandonThroughTheScreen`.
- Whole suite passed: `backlog/log/check/20261025T183450150971.log`.

## Review

No defects found. The change is sound.

Criteria satisfied, with evidence:

1. `workflows/default.json` gives `accept` exactly `pr`, `revise`, `abandon`. Proven by `tests.test_workflow.WorkflowDefinition.test_pr_decision_gates_completion_after_publish`, `tests.test_pr_decision` (refusal of `accept` as "not a transition") and `tests.test_abandon`.
2. `pull-request` offers `merged`, `rejected`, `abandon`. Proven by the same workflow test and the journey test in `tests/test_abandon.py`.
3. Both steps lead to `abandoning` (`harness:abandon`), then `abandoned`; `done` is reached only from `merged`. Proven by `test_both_customer_steps_abandon_and_only_merged_reaches_done` and the journey test.
4. `abandon` in `devteam/runner.py` switches to the recorded base and never deletes the branch. Proven by `test_clean_checkout_returns_to_base_and_next_item_starts_there` and the journey test.
5. A dirty tree raises `StepFailed` naming the branch before any switch; `uses_checkout` includes `abandon`, so the item holds the checkout. Proven by `test_dirty_tracked_and_untracked_fail_hold_checkout_and_retry` and `test_abandon_is_serialised_with_other_checkout_work`.
6. The function returns `completed` early when the current branch is not `devteam/<id>`. Proven by `test_other_checkout_is_untouched_even_dirty_and_without_recorded_base`.
7. A missing base fails with the branch name and no switch. Proven by `test_missing_base_fails_on_item_branch_without_switching`.
8. The action runs only local branch, status and switch commands. No test of absence; I accept the recorded reason, as the diff shows nothing else is called.
9. Proven by `test_clean_checkout_returns_to_base_and_next_item_starts_there` and the "other checkout" test.
10. The TUI note skip is extended in `devteam/tui.py`. Proven by the tester's journey test `AbandonThroughTheScreen`. The finished display of `abandoned` uses the existing terminal-step handling; I accept the recorded presentation reason.
11. Proven by `test_existing_done_accept_and_pull_request_items_remain_valid`.
12. README table and prose updated, including that closing the PR is the customer's job; no mention of accepting without a PR remains. Accepted as presentation, judged from the diff.
13. `tests/test_workflow.py` and `tests/test_pr_decision.py` updated.

Whole suite passed: `backlog/log/STORY-027/verify-20261025T183719547401.log` (319 tests, OK).

Minor, not blocking: `abandon` checks the recorded base before the clean tree, so a branch with both problems reports the base first. Both surface on retry.

## Test run

Run by the harness, 2026-10-25 18:39:37 UTC: passed (exit 0); duration 137.883 seconds.
