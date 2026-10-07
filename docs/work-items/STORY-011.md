---
id: STORY-011
type: story
title: Bring local main in line with origin when a PR is merged
parent: EPIC-003
workflow: default
step: publish
---
As the customer, I want local main brought in line with origin when I mark a PR merged, so that my checkout reflects what I merged.

## Original criteria

- Moving to `merged` fetches origin and fast-forwards the base branch.
- The item ends at a terminal step.
- If main has diverged or the checkout is dirty, the step fails with a message naming the cause and leaves the repository untouched.
- Tested against a local bare remote.

## Analysis

### What exists today

- Nothing implements this yet. `workflows/default.json` has `publish` -> `done`; there is no `pull-request`, `merged` or harness-owned step. STORY-010 (at `ready`, not built) adds `pull-request` -> `merged` (owner `harness:merged`, transition `completed` -> `done`) with a placeholder action that only returns `completed`, and a registry in `devteam/runner.py` mapping action name to function. STORY-011 is blocked on STORY-010 and replaces the `merged` placeholder body. It must not be played before STORY-010 lands.
- `devteam/git.py` has `must`, `run`, `clean` (`status --porcelain`, so untracked files count), `current_branch`, `has_ref` and `base_of` (reads `branch.<branch>.base`, recorded by `take_checkout` when the item's branch is created). It has no fetch or fast-forward helper.
- `Runner.run_item()` already turns `StepFailed` and `git.GitError` into: item left at its step, message reported as `FAILED - <reason>; still at <step>`, no retry until `retry()` or restart. That is the "step fails" behaviour the item asks for.
- `take_checkout` holds the checkout on `devteam/<id>` until the item is at a terminal step. At `merged` the item is not yet terminal, so the checkout is still on the item's own branch (not on the base) when the action runs. This matters: a branch checked out in the working tree cannot be updated by `git fetch origin main:main`, so the action has to switch the checkout to the base branch to fast-forward it.
- Tests use real git against a local bare remote (`tests/test_checkout.py` builds `remote.git` and a `product` clone), so the "tested against a local bare remote" criterion follows an existing pattern.

### What would change

1. `devteam/git.py`: helpers to fetch a remote and to fast-forward a local branch.
2. `devteam/runner.py`: the `merged` action, for item `devteam/<id>`:
   1. Resolve the base with `git.base_of`; if none is recorded, raise `StepFailed` (existing wording).
   2. If the checkout is not clean, raise `StepFailed` naming uncommitted changes and the branch. It fails rather than waits (`Waiting` is what `take_checkout` uses; it would leave the item silently retrying, which is not what the item asks for).
   3. `git fetch origin`; failure (no `origin`, unreachable) raises `StepFailed` quoting git's message.
   4. Check that local `<base>` and `origin/<base>` both exist; if either is missing, raise `StepFailed` naming the missing ref. Then compare the two, three cases:
      - local `<base>` is an ancestor of (or equal to) `origin/<base>`: go to step 5.
      - `origin/<base>` is an ancestor of local `<base>` and they differ (local is only ahead): succeed (customer's answer to Question 1). No ref moves; go to step 5, where `merge --ff-only` reports "Already up to date".
      - neither is an ancestor of the other: raise `StepFailed` saying the base has diverged from origin.
   5. Switch the checkout to `<base>` and `merge --ff-only origin/<base>`.
3. Tests in `tests/test_runner.py` (or a new `tests/test_merged.py`) using a local bare remote.
4. `README.md`: say that `merged` brings the local base branch in line with origin and that it fails on a dirty or diverged checkout.

### Assumptions (stated, not questions)

- "Base branch" is the one recorded in `branch.devteam/<id>.base`, not a hard-coded `main`; the remote ref is `origin/<base>`, with the remote named `origin` as everywhere else in the harness.
- "Leaves the repository untouched" means: HEAD, the current branch, every local branch ref and the working tree and index are unchanged. `git fetch` necessarily updates `refs/remotes/origin/*`; that is allowed, and the criteria say so. Checks run in the order clean, fetch, diverged, so the dirty check happens before any change at all, and a diverged result happens before the switch.
- On success the checkout ends on the base branch (a consequence of having to switch to fast-forward it). The item's branch is left in place, not deleted.
- Local base equal to `origin/<base>` succeeds ("already up to date"). Local base that contains everything on `origin/<base>` plus unpushed commits also succeeds and keeps those commits (customer's answer to Question 1). Only "diverged" (each side has commits the other lacks) and "dirty" are failures.
- A failed `merged` step leaves the checkout on `devteam/<id>` with the item at `merged` (not terminal), so `take_checkout` makes every other code-changing item wait until the customer fixes the cause and retries (key `t` in the TUI, or `retry()`). This is existing behaviour and is accepted; the customer was shown it in Question 1 and did not object.
- A squash or rebase merge on GitHub is fine: origin's base simply moves forward and fast-forwards cleanly provided local base had no extra commits.
- The tool does not check that the PR is actually merged on GitHub (stated in STORY-010); only git state is examined.
- After failure the customer fixes the cause and retries via restart or `retry()`, the existing mechanism. No new retry control is in scope.
- The step does not take the checkout via `take_checkout` and does not count a run (STORY-010 criterion 13 stays true for this action's bookkeeping; it just does git work on the existing checkout).

### Risk

- The checkout may be on a branch that is not the item's (customer switched by hand). The action still operates on the base recorded for the item's branch and switches away from whatever is checked out, provided it is clean. Covered by criterion 14.
- A failure holds the checkout and so blocks other code-changing items (see assumptions). Criterion 15 pins it and the README says how to recover.
- On failure the report ends with a log pointer and the TUI wording says an agent failed, though no agent or log exists for a harness action. Accepted as STORY-010's concern; criterion 11 pins only the `FAILED - <reason>; still at merged` part, not any log path.

## Acceptance criteria

This list supersedes the "Original criteria", all of which it covers. Dependency, not a criterion: STORY-010 must land first (`merged` harness-owned, transition `completed` -> `done`); this story replaces its placeholder body rather than adding a second action. Tests use real git: a bare remote, a product clone, and a second clone used to advance or diverge origin's base. "Unchanged" below means: HEAD, the checked-out branch, `git status --porcelain`, file contents, and every branch ref other than `devteam-backlog` (the backlog branch may receive the harness's own failure commit). `refs/remotes/origin/*` may be updated by the fetch.

1. Replacing the placeholder: `grep` finds exactly one registered `merged` action in `devteam/runner.py`, and it performs the git work below.
2. Success: with a clean checkout on `devteam/<id>` and origin's base ahead of local base, running the `merged` step leaves local `<base>` at the same commit as `origin/<base>`, the checkout on `<base>`, and the item at `done` (a terminal step, `terminal` true). The `devteam/<id>` branch still exists.
3. Already in line: local base equals origin base; the step completes, the item reaches `done`, no branch moves.
4. Dirty: with a modified tracked file or an untracked file in the checkout, the step raises `StepFailed`; the reported message contains "uncommitted" and the branch name; the item stays at `merged`; everything is unchanged.
5. Diverged: with a commit on local base and a different commit on origin's base, the step fails with a message containing "diverged" and the base branch name; item stays at `merged`; everything is unchanged.
6. Local base strictly ahead of origin (contains all of `origin/<base>` plus unpushed commits, nothing new on origin): the step completes, the item reaches `done`, the checkout ends on `<base>`, and local `<base>` still points at its own unpushed tip commit (not reset to origin).
7. Fetch failure (remote missing or path invalid): the step fails with a message quoting git's error; item stays at `merged`; everything is unchanged.
8. No base recorded for the item's branch: the step fails with the existing "no base branch is recorded" message; nothing changes.
8a. Missing ref: if `origin/<base>` does not exist after fetch, or local `<base>` does not exist, the step fails with a message naming that ref; item stays at `merged`; everything is unchanged.
9. A failed `merged` step is recorded in `Runner.failed`, is not retried by `run_pass()`, and runs again after `retry(id)`; a test fixes the cause (cleans the checkout) and sees it succeed.
10. A test asserts no engine is invoked and a `gh` stub placed first on `PATH` records no call during the action; `grep` finds no `gh pr merge` in `devteam/`.
11. The failure message and the success report appear in the runner's `report` output in the existing `<id> merged ...: FAILED - ...` / `completed -> done` format (asserted on the messages list).
12. `README.md` describes the `merged` behaviour, including both failure causes (dirty, diverged) and how to recover (fix the cause, press `t` or call retry).
13. `uv run python -m devteam check` passes.
14. Checkout on neither the item's branch nor the base, and clean: the step switches to base and fast-forwards, item reaches `done`. One test.
15. After a failed `merged` step the checkout is still on its pre-step branch and another code-changing item's `take_checkout` still waits; after the cause is fixed and `retry(id)` succeeds, the item is terminal and the other item can take the checkout.

## Challenge response

1. Local-ahead behaviour: asked as Question 1; the customer answered "succeed", and step 2.4, the assumptions and criteria 3 and 6 now reflect that.
2. Blocking consequence: stated in the assumptions, added as criterion 15 and in the README recovery text (criterion 12), and mentioned in Question 1.
3. Step 2.4 rewritten as three cases.
4. "Unchanged" scoped to exclude `devteam-backlog`.
5. Criterion 8a added for missing refs.
6. (a) first list renamed "Original criteria"; (b) criterion 1 now a dependency note plus a checkable grep; (c) criterion 10 specifies a `gh` stub; (d) log-path wording accepted, recorded under Risk; (e) criterion 14 added.

## Questions

1. If your local main already has everything on origin plus commits of your own that you have not pushed, should marking the PR merged succeed (nothing to pull, your commits stay) or fail until you push? Note that a failed merge step keeps the checkout on the item's branch and makes every other code-changing item wait until you fix the cause and retry, so failing here would stop the pipeline until you push. My recommendation is to succeed.

   **Answer:** It should succeed provided it contains what is currently on origin/main even if it has additional commits that have not been pushed.

## Challenge

Outcome: sound. A competent engineer could build this as written and a reviewer could judge it against criteria 1 to 15. All six findings of the earlier challenge are dealt with: the one that needed the customer is answered under Questions ("succeed"), and step 2.4, the assumptions and criteria 3, 6, 8a, 14 and 15 match that answer. Checked again against the repository: `workflows/default.json` still ends `publish` -> `done` with no harness step; `devteam/git.py` has `clean`, `current_branch`, `has_ref`, `base_of` and no fetch or fast-forward helper; `Runner.run_item` (`devteam/runner.py:191-198`) reports `FAILED - <reason>; still at <step>` and `pending()` skips failed items until `retry()`; `take_checkout` (`devteam/runner.py:85-88`) releases only on a terminal step; key `t` is bound to retry (`devteam/tui.py:355`); `tests/test_checkout.py` builds a bare `remote.git`. Each criterion traces to the customer's four original criteria, to the answer to Question 1, or to STORY-010's contract.

The following do not change what is built or how it is judged. They are recorded so nobody is surprised later.

1. **"The action has to switch the checkout to the base branch to fast-forward it" is wrong as reasoning, though the outcome stands.** "What exists today" argues that a checked-out branch cannot be updated by `git fetch origin main:main`, and in the same paragraph says the checkout is on `devteam/<id>`, not on the base. With the base not checked out, `git fetch origin <base>:<base>` would fast-forward it without touching the working tree, so the switch is a choice, not a necessity. The choice is the right one: the customer wrote "so that my checkout reflects what I merged" and asked for a dirty checkout to fail, which only makes sense if the working tree moves. Criteria 2, 6 and 14 pin "the checkout ends on `<base>`", so nothing is left to interpretation; the engineer should simply not treat the stated reason as a constraint.

2. **The most likely recovery state has no test.** After a "diverged" failure the customer will switch to the base by hand, rebase or merge, and press `t`; the checkout is then already on the base. Criterion 2 starts on `devteam/<id>`, criterion 14 on "neither", and criterion 15's recovery only cleans a dirty checkout. The steps as written handle it (the switch is a no-op, `merge --ff-only` fast-forwards or reports up to date), so this is a missing test, not missing behaviour. A reviewer can ask for one case: checkout on `<base>`, clean, step completes.

3. **STORY-010's own tests will need changing and the item does not say so.** STORY-010 criterion 13 has each harness action "only return `completed`", and its criterion 7 test will most likely run an item at `merged` with no checkout or no recorded base. Once the body is replaced that test fails with "no base branch is recorded". Normal work for the implementer, and criterion 13 here (`devteam check` passes) forces it, but the claim under Assumptions that "STORY-010 criterion 13 stays true" holds only for the bookkeeping half. Related: a `Runner` built with `checkout=None` has no criterion; `git.base_of(None, ...)` returns nothing, so it would surface as the "no base branch is recorded" message, which names the wrong cause. Cosmetic; `take_checkout` already has wording for it ("needs a git repository") if the engineer wants it.

4. **Small leftovers.** Criterion 4 says the message contains "the branch name" without saying which; the checked-out branch is the only sensible reading and matches `take_checkout`'s wording. Criterion 1's "`grep` finds exactly one registered `merged` action" depends on the registry shape STORY-010 chooses, so it can only be made exact once that lands. The squash-merge assumption is correct for the base; note that `devteam/<id>` will then look unmerged to git, and the item deliberately leaves that branch in place.

Sound as written: the three-way ancestry comparison in step 2.4 matches what `git merge --ff-only` does in each case; the check order clean, fetch, compare, switch leaves HEAD, the branch refs and the working tree untouched on every failure path; "unchanged" is now scoped to exclude `devteam-backlog`, which `run_item` may commit to on failure; failing a diverged base, with the pipeline held until it is fixed, is the customer's own criterion and they were shown the blocking consequence in Question 1.

Cheapest way to be wrong: the dependency. Everything here assumes STORY-010 lands with `harness:merged`, a registry in `devteam/runner.py` and `completed` -> `done`. Before playing, `grep -n harness workflows/default.json devteam/runner.py` settles in a second whether that is true.

## Implementation

Implemented the replacement of STORY-010's single registered `merged` placeholder. STORY-010 is now present on this branch, so the previous dependency block is resolved. No commits were made; changes are left in the working tree.

- The action resolves the base recorded for `devteam/<id>`, rejects a dirty checkout before fetching, fetches `origin`, validates both base refs and their ancestry before switching, and switches to the base for `merge --ff-only`. Equal and ahead-only local bases succeed without losing unpushed commits. Diverged bases, missing refs/configuration and fetch errors use the runner's existing failure handling. A missing checkout reports that the step needs a git repository.
- Added focused real-git tests using a local bare remote, product clone and writer clone for the ancestry cases, dirty tracked/untracked files, missing refs/base, fetch failure, unchanged checkout on failure and retry/checkout release. Success is exercised from the item's branch, the base itself and an unrelated branch. The tests also check report messages, terminal completion, no engine/run count and no invocation of a `gh` stub.
- Updated STORY-010's existing tests for the new repository requirement; the generic harness retry test uses the still-placeholder rejected action. The existing CLI merged test now has a real git repository and remote.
- Updated README behaviour and recovery instructions (fix the cause, press `t` or call `Runner.retry(id)`).

Criterion 13 remains unverified: the project-wide check did not finish in this session. It was interrupted with exit 130 and no output. A separate bounded verbose diagnostic run also stopped progressing after the existing `test_requests.NewRequestUI.test_new_request_preserves_text_and_derives_title` reported `ok`. No unrelated application code or tests were changed to bypass this. The tester's full-suite run must establish the project check result; this is not reported as a pass.

### Checks and actual output

First focused run, `UV_CACHE_DIR=/tmp/devteam-uv-cache uv run python -m unittest tests.test_merged tests.test_runner tests.test_pr_decision tests.test_checkout`, exited 1. Its failing fixture attempted to use the previously non-git backlog after initializing git. That fixture was corrected to create a real backlog worktree and restore the captured items there. Actual failure output (traceback excerpt):

```text
..........................E...............
======================================================================
ERROR: test_merged_decision_is_completed_by_the_harness_without_an_agent (tests.test_pr_decision.PullRequestDecision.test_merged_decision_is_completed_by_the_harness_without_an_agent)
----------------------------------------------------------------------
subprocess.CalledProcessError: Command '['/home/tarttelin/projects/pyruby/dev-team/.venv/bin/python3', '-m', 'devteam', '--product', '/tmp/tmph9hu94ss/product', 'backlog', 'move', 'STORY-001', 'analyse']' returned non-zero exit status 1.

----------------------------------------------------------------------
Ran 43 tests in 12.925s

FAILED (errors=1)
```

After the correction, the same command exited 0:

```text
...........................................
----------------------------------------------------------------------
Ran 43 tests in 12.579s

OK
```

After final test cleanup, the same command exited 0:

```text
...........................................
----------------------------------------------------------------------
Ran 43 tests in 13.802s

OK
```

`UV_CACHE_DIR=/tmp/devteam-uv-cache uv run python -m devteam check`: interrupted, exit 130, no output. It captures the child process output until completion, so there is no suite verdict from this invocation.

`UV_CACHE_DIR=/tmp/devteam-uv-cache timeout 180s uv run python -m unittest discover -s tests -v > /tmp/story-011-suite.log 2>&1`: interrupted, exit 130, before the timeout. The log contains successful test results through the following lines, then no further progress or final verdict:

```text
test_item_awaiting_the_customers_pull_request_decision_blocks_other_code_changes (test_pr_decision.PullRequestHoldsTheCheckout.test_item_awaiting_the_customers_pull_request_decision_blocks_other_code_changes) ... ok
test_new_request_preserves_text_and_derives_title (test_requests.NewRequestUI.test_new_request_preserves_text_and_derives_title) ... ok
```

`rg -n 'gh pr merge|HARNESS_ACTIONS =' devteam` exited 0, showing one merged registration in the runner and no `gh pr merge`:

```text
devteam/workflow.py:11:HARNESS_ACTIONS = {"merged", "rejected"}
devteam/runner.py:60:HARNESS_ACTIONS = {"merged": merged, "rejected": rejected}
```

`git diff --check` and `git -C backlog diff --check` exited 0 with no output.

## Tests

Whole suite: `uv run python -m devteam check` (128 tests, passing). One module or test: `uv run python -m devteam check tests.test_merged_cli` or `uv run python -m devteam check tests.test_merged_cli.MergedFromTheCommandLine.test_diverged_main_fails_the_step_and_leaves_the_repository_untouched`.

`tests/test_merged_cli.py` starts `python -m devteam` as a subprocess against a bare remote, a product clone and a second writer clone, with a `claude` stub and a `gh` stub that records calls. `tests/test_merged.py` (the implementer's) covers the same behaviour in-process against real git.

- 1 (one registered action, no `gh pr merge`): `MergedSourceAndDocumentation.test_exactly_one_merged_action_is_registered_and_no_pr_is_merged_by_the_tool`
- 2 (success, branch kept, terminal): `test_merged_fast_forwards_local_main_to_origin_and_finishes_the_item`; in-process `test_merged.Merged.test_origin_ahead_from_item_base_or_unrelated_checkout`
- 3 (already in line): `test_merged_succeeds_when_main_already_matches_origin`; `test_merged.Merged.test_equal_and_local_ahead_keep_local_commits`
- 4 (dirty tracked and untracked): `test_dirty_checkout_fails_the_step_and_leaves_the_repository_untouched`; `test_merged.Merged.test_dirty_tracked_and_untracked_fail_before_fetch`
- 5 (diverged): `test_diverged_main_fails_the_step_and_leaves_the_repository_untouched`; `test_merged.Merged.test_diverged_fails_before_switch`
- 6 (local ahead kept): `test_merged_keeps_unpushed_local_commits_on_main`
- 7 (fetch failure): `test_unreachable_origin_fails_the_step_and_leaves_the_repository_untouched`; `test_merged.Merged.test_fetch_failure_preserves_checkout`
- 8, 8a (no base, missing refs): `test_merged.Merged.test_missing_base_and_refs_preserve_checkout`
- 9 (failed, not retried, retried after fix): `test_failed_step_is_retried_after_the_cause_is_fixed_by_restarting`; `test_merged.Merged.test_dirty_tracked_and_untracked_fail_before_fetch`
- 10 (no engine, no `gh`): `assert_not_invoked` in every CLI test; `test_merged.Merged.done`
- 11 (report format): CLI tests assert the `completed -> done` and `FAILED - ...; still at merged` output; `test_merged.Merged.done`/`failed`
- 12 (README): `MergedSourceAndDocumentation.test_readme_describes_merged_failures_and_recovery`
- 13: the full suite passes.
- 14 (checkout on neither branch): `test_merged.Merged.test_origin_ahead_from_item_base_or_unrelated_checkout` (subcase `other`)
- 15 (checkout held after failure, released after retry): `test_merged.Merged.test_dirty_tracked_and_untracked_fail_before_fetch`

## Test run

Run by the harness, 2026-10-07 13:55 UTC. Full output: `/home/tarttelin/projects/pyruby/dev-team/backlog/log/STORY-011/verify-20261007T135412591108.log`

Passed: `the project check`

```text
uv run python -m unittest discover -s tests
..........................................................................................................Executing <Task pending name='message pump Actions()' coro=<MessagePump._process_messages() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/message_pump.py:571> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.123 seconds
......................
----------------------------------------------------------------------
Ran 128 tests in 71.726s

OK
```

## Review

Outcome: approve. No finding that blocks acceptance. The harness's own run (128 tests, OK) is the evidence relied on; the implementer's "criterion 13 unverified" note is superseded by it.

Minor observations (none require a change):

1. `tests/test_merged.py::test_origin_ahead_from_item_base_or_unrelated_checkout` resets state between subcases with `update-ref refs/remotes/origin/main`, which is fragile if a subcase fails midway; it passes and the three starting points (item branch, base, unrelated branch) are genuinely exercised.
2. A detached HEAD would report the dirty message with whatever `current_branch` returns for it; cosmetic only.
3. `tests/test_pr_decision.py` now builds a git repository by hand in the middle of the test (renames the backlog, inits, copies back). Awkward but needed because `merged` now requires a repository.

Criteria satisfied, with evidence:

- 1: `devteam/runner.py:60` registers one `merged`; `merged()` does the git work; `test_exactly_one_merged_action_is_registered_and_no_pr_is_merged_by_the_tool` greps for it and for `gh pr merge`.
- 2, 3, 6, 14: `git.fast_forward` checks ancestry both ways, then switches and `merge --ff-only`. `test_origin_ahead_from_item_base_or_unrelated_checkout` (item branch, base, other), `test_equal_and_local_ahead_keep_local_commits`, and the CLI tests against a real bare remote assert the base tip, checkout on base, `done`/terminal, item branch kept, unpushed tip preserved. The "already on base" recovery state is covered by the `main` subcase.
- 4: clean check precedes fetch; message "uncommitted changes on devteam/<id>"; tracked and untracked tested in-process and via CLI with a before/after snapshot.
- 5: "base branch main has diverged from origin/main", raised before any switch; snapshot unchanged in both test files.
- 7: `must` fetch error quoted; tested with a bad remote URL and snapshot comparison.
- 8, 8a: base check first; missing local and missing remote refs each name the ref (`test_missing_base_and_refs_preserve_checkout`).
- 9, 15: `failed()` asserts `Runner.failed` entry, no re-run in `run_pass`, `take_checkout` still waits, then `retry` after cleaning succeeds and the other item takes the checkout.
- 10: engine that fails if called, `gh` stub recording calls on PATH, no `gh pr merge` in source.
- 11: report strings `completed -> done` and `FAILED - ...; still at merged` asserted on the messages list and CLI output.
- 12: README describes fetch, fast-forward, both failure causes, and recovery with `t` or `retry`; a test checks key phrases.
- 13: harness run passed.

TRANSITION: approve
