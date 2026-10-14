---
id: STORY-020
type: story
title: Run non-branch agent steps in parallel
parent: EPIC-007
workflow: default
step: publish
---
**As a** customer running `dev-team` with several requests and stories in flight
**I want** agent steps for roles without their own branch to run concurrently, one step per item
**So that** a long analysis on one item does not block others, including questions I could be answering

## Context

Today `Runner.run_pass` and the TUI `agent_loop` run one step at a time, with a single `active` item id. Roles with `branch = true` take the checkout via `take_checkout` and stay serial. Roles without it (product_owner, analyst, challenger, architect, platform_engineer, quality_lead) are parallelisable. `check` and `harness` steps are unchanged. Depends on the cross-process write lock story. Analysis agents read whatever the checkout currently holds (customer decision); this is documented, not engineered around.

## Analysis

Findings against the repository:

- The premise holds. `Runner.run_pass` (`devteam/runner.py:356`) runs `run_item` over `pending()` one at a time. `Runner.active` is a single id or `None`, set in `invoke` (`:261`) and `verify` (`:295`) and cleared in `finally`. The TUI's `agent_loop` (`devteam/tui.py:630`) is its own serial copy of the loop, and headless `Runner.run` (`:359`, called from `devteam/cli.py:57`) uses `run_pass`.
- `Role.branch` (`devteam/config.py`) is true for implementer, tester, reviewer and publisher; the six roles named in the item have it false. `check` steps call `take_checkout` (in `verify`) and the `merged` harness action switches the checkout to the base branch, so both are checkout users too, not only branch roles.
- `take_checkout` is a check-then-switch with no lock (`:196-223`). Called from two threads at once, two items could both see a free checkout and both switch it. `Waiting` alone is not race-free, so checkout-using steps need mutual exclusion (criterion added).
- Non-branch roles run with `cwd` set to the checkout (`:266`) but never call `take_checkout`; they read whatever branch is current. The customer has accepted this.
- Shared mutable state today: `failed`, `waiting`, `runs` (`count_run` is a read-modify-write) and `active`. Backlog writes are serialised in-process by `WRITE` (`devteam/backlog.py:57`), which already covers worker threads in one process.
- `on_line` is a single-argument callable, set by the TUI at `tui.py:448` and passed to `engines.run` only when set (`runner.py:264`). The engine contract stays `on_line(line)`; the runner must bind the item id per step and call the registered callback with `(item_id, line)`. The `Acting` fixture and `tests/test_engines.py:127` use the one-argument form and need updating.
- Consumers of `active`: `tui.py:99` (`runner.active == record.id`), `:662-663` (stop message), `:686-687` (quit confirmation), `tests/test_launcher.py:180` (`assertIsNone(runner.active)`).
- `run_pass` returns a count that tests rely on (`tests/test_merged.py:69,81,87`, `tests/test_requests.py:36,167`), and `run(once=True)` is used widely (`tests/test_checkout.py`, `test_requests.py`, `test_engines.py`). They must keep passing, so with a single runnable item the dispatcher behaves as today.
- The current dirty-checkout message is "waiting: the checkout has uncommitted changes on <branch>", and `tests/test_checkout.py:161` asserts `"uncommitted changes"`. The "checkout not clean" wording the item asks for is therefore added alongside, not instead.
- Dependency: STORY-019 (cross-process write lock) is now implemented on this branch, so agents' own `dev-team` subprocesses are serialised across processes. This story can be built and tested with fake engines.

Decisions I am comfortable stating (not questions):

- There is no cap on concurrent agents and no `max_agents` setting. The earlier cap came from the analysis, not the customer (see Feedback); how many items to put in flight is the customer's choice. Concurrency is bounded only by the number of items with a runnable step, and by the single checkout (next point). Nothing in the config or README mentions a cap.
- STORY-019 has landed on this branch (`fcntl.flock` on `log/backlog.lock` in `devteam/backlog.py:65-84`), as the customer answered. The dependency is satisfied, so no interim default is needed.
- At most one checkout-using step (branch-role step, `check` step, `merged` harness action) runs at a time, enforced by a lock around the step rather than only around `take_checkout`. A step that cannot get the checkout reports `Waiting` as today instead of blocking a worker. The `rejected` harness action does not touch the checkout and may run alongside.
- The dispatcher lives in `Runner` and is used by both the TUI and `dev-team run`; `tui.agent_loop` stops duplicating the loop. Workers are threads. `run_pass` keeps returning the number of steps completed.
- Stop prevents new submissions only. There is no kill, and a later Start while steps are still running must not start a second step for those items.
- Not retrying a failed item until restart is existing behaviour (`retry()` in the TUI remains).

## Acceptance Criteria

- [ ] **Given** two items pending at non-branch agent steps and a fake engine whose calls block on `threading.Event`s, **When** the runner dispatches, **Then** both engine calls are in progress at the same time before either is released.
- [ ] **Given** four items pending at non-branch agent steps and a fake engine whose calls block on `threading.Event`s, **When** the runner dispatches, **Then** all four engine calls are in progress at the same time; no limit on their number is applied and `config/roles.toml` has no `max_agents` key.
- [ ] **Given** an item with a running step, **When** a further pass looks for work, **Then** it does not start a second step for that item, including after Stop then Start in the TUI while the first step is still running.
- [ ] **Given** a branch-role step is running and holds the checkout, **When** another branch-role step is pending, **Then** that item reports waiting with the reason "waiting for <id>, which is using the checkout" (<id> being the running item) and does not run, while non-branch steps still run alongside it. The existing `take_checkout` messages ("waiting for <holder>, which holds the checkout at step <step>" and the uncommitted-changes message) are used only when no step is running, i.e. the checkout is left on another unfinished item's `devteam/` branch or is dirty.
- [ ] **Given** two branch-role (or check) steps for different items are pending in the same pass with a free checkout, **When** dispatching, **Then** exactly one takes the checkout and runs, the other reports the same "waiting for <id>, which is using the checkout" reason, and the checkout is never switched by both. A step turned away by the step lock does not count as completed and does not set `failed`.
- [ ] **Given** a branch-role or check step is running and holds the checkout, **When** an item is pending at a `merged` harness action (`merged` in `devteam/runner.py:52-65`, which runs `git.fast_forward` and so switches the checkout to the base branch), **Then** the `merged` step reports "waiting for <id>, which is using the checkout", does not raise `StepFailed`, does not mark the item failed, and does not switch the checkout's branch; once the running step ends it runs on a later pass. Conversely, while a `merged` step is running, a branch-role or check step is turned away with the same reason. The `rejected` harness action does not touch the checkout and may run alongside any of these; this is a choice, not an omission.
- [ ] **Given** the continuous dispatcher (the TUI agent loop, and `dev-team run` without `--once`), which is a different path from the synchronous `run_pass`, **When** item A's agent step is blocked on a `threading.Event` and item B then becomes runnable afterwards (created, answered, or moved to a non-branch agent step), **Then** B's step starts before A is released. This is checked for the dispatcher as driven by the TUI and as driven by `dev-team run`; a submit-everything-then-join loop does not satisfy it.
- [ ] **Given** one item's step fails, **When** others are running or pending, **Then** the others continue, and the failed item is not retried until restart (or `retry`), as today.
- [ ] **Given** a worker step raises an exception other than the ones `run_item` already handles, **When** it escapes, **Then** it is reported with the item id, the item is marked failed (not retried until restart or `retry`), the dispatcher and other items' steps carry on, and the exception is never left unread on a future. This replaces today's "agents stopped after an error" stop of the whole loop, which makes no sense with several steps in flight.
- [ ] **Given** `Runner.active`, **When** consumers read it, **Then** it is a set of running item ids exposed through a read-only `active_ids()` returning a sorted list copy; the TUI running marker uses membership, the Stop message names all running ids, and the quit confirmation is requested when any are running and names them all. `tests/test_launcher.py` and any other test comparing `active` to a string or `None` are updated.
- [ ] **Given** `failed`, `waiting`, `runs` and `active`, **When** written from several threads, **Then** every access is guarded by one runner lock, so `count_run` cannot lose an increment and `max_runs` is honoured under concurrency.
- [ ] **Given** agent output from concurrent steps, **When** shown in the TUI output pane, **Then** each line is prefixed with its item id, e.g. `STORY-004 | ...`, produced from a runner `on_line` callback that receives `(item_id, line)`. The engine-level `on_line(line)` contract is unchanged, and a runner with no listener still passes none to the engine.
- [ ] **Given** Stop in the TUI, **When** pressed, **Then** no new steps start and running agents finish; none are killed. The dispatcher loop (and so `self.thread`) ends immediately on Stop, without waiting for running steps. While any step is still running the Agents title reads "stopping - waiting for <ids>" (all running ids); once none are running it reads the existing "stopped - s to start" text, refreshed when the last step finishes. Pressing `s` during the drain starts the dispatcher again; it does not start a second step for any item still running (the earlier criterion on running items).
- [ ] **Given** headless `dev-team run`, **When** run, **Then** it uses the same dispatcher (continuous without `--once`; `run_pass` and `run(once=True)` are synchronous wrappers that wait for every step they submit). `run_pass` returns the number of steps that ran to a transition or to a failure; a step that reported `Waiting` is not counted. `run(once=True)` returns when a pass completes no step and no submitted step is still in flight, so an item that is waiting (as in `tests/test_checkout.py:133-138`, where each call must return) never keeps it looping. A step that finishes while others are in flight may make another item runnable, which is then run before returning. Existing serial tests pass unchanged apart from the `active` updates.
- [ ] **Given** the dirty-checkout case, **When** a branch-role or check step cannot take the checkout under the dispatcher, **Then** the existing "waiting: the checkout has uncommitted changes on <branch>" reason is reported, as asserted by `tests/test_checkout.py:161`. No new wording is added.
- [ ] **Given** a non-branch agent and a branch-role agent running at the same time, **When** the branch-role step ends and commits, **Then** the branch-role step's commit may include files a non-branch agent wrote to the checkout meanwhile; this is accepted (Question 2) and no check or refusal is added to the end-of-step commit.
- [ ] The README documents that non-branch agents run in parallel, that analysis agents may see the checkout's branch change mid-step, and that a stray file written by a parallel non-branch agent can be committed onto a running branch-role item's branch.
- [ ] `dev-team check` passes.

## Response to the challenge

- Finding 1: accepted. The `--once` and `run_pass` criterion now counts failures and excludes waits, matching `runner.py:335-339` and the `tests/test_checkout.py:133-138` case.
- Finding 2: put to the customer as Question 1. If parallel agents may ship first, a criterion will make the default `max_agents` 1 until STORY-019 lands.
- Finding 3: confirmed. `commit_all` at `runner.py:281-282` stages the whole tree, so a parallel analyst's stray file would land on another item's branch. Put to the customer as Question 2.
- Finding 4: accepted; criterion added. Marking the item failed is chosen because stopping everything would defeat the parallelism.
- Finding 5: accepted. The dispatcher loop ends on Stop; the drain is shown as "stopping" in the title and Start is allowed during it, which makes the Stop-then-Start clause reachable.
- Finding 6: accepted; the reason text is now stated in the checkout-race criterion.
- Finding 7: accepted; the "checkout not clean" wording is dropped in favour of the existing message.

## Response to the feedback

- The agent cap was not asked for by the customer. Removed: the `max_agents` decision, the two cap criteria (replaced by one criterion that all runnable non-branch steps run together), and the README mention. The single-checkout exclusion stays, since it prevents a real race rather than limiting cost.
- Question 1 answered: STORY-019 lands first, and it is present on this branch. Question 2 answered: risk accepted; the matching criterion and README line are fixed accordingly.
- Nothing remains to ask the customer.

## Response to the second challenge

- Finding 1: accepted. A criterion now requires that an item becoming runnable while another step is blocked starts at once, for the TUI and `dev-team run`. The continuous dispatcher is stated to be a separate path from `run_pass`; `run_pass` and `run(once=True)` stay synchronous because tests assert state straight after they return. The current `run` loop (`devteam/runner.py:359`) sleeps `interval` between passes, so the continuous path must poll or be woken while steps are in flight rather than join them.
- Finding 2: accepted. One reason, "waiting for <id>, which is using the checkout", covers every step turned away by the step lock (both criteria now say so). The `take_checkout` messages remain for the case where no step is running but the checkout is on another unfinished item's branch or is dirty; `tests/test_checkout.py:161` is unaffected because no step is running there.
- Nothing remains to ask the customer.

## Response to the third challenge

- Finding 1: accepted. A new criterion names the `merged` action: it waits (not fails, not switches branch) while another checkout-using step runs, and turns away branch-role and check steps while it runs. `rejected` is stated to run alongside by choice. The existing `StepFailed` for a dirty checkout in `merged` (`runner.py:60-62`) stays for the case where no step is running.
- Nothing remains to ask the customer.

## Questions

1. Should parallel agents ship only after STORY-019 (the cross-process write lock) has merged? If they may ship first, the default `max_agents` would be 1 until STORY-019 lands, so nothing runs in parallel by default.

   **Answer:** Story-019 will land first
2. While a non-branch agent (such as the analyst) runs alongside a branch-role agent (such as the implementer), a stray file written by the analyst would be committed onto the implementer's feature branch under its commit message, and may be pushed. Prompts tell analysts not to edit code but nothing enforces it. Do you want (a) to accept this and document it in the README beside the mixed-branch read, or (b) the branch-role end-of-step commit to refuse and report changes it did not expect, leaving the item waiting for you?

   **Answer:** I accept this risk.

## Challenge

Sound: a competent engineer could build this as written, and a reviewer could tell whether they had.

The customer's feedback has been acted on. The agent cap, `max_agents` and the README mention of a cap are gone. The criterion with four items now requires that no limit is applied. The one remaining restriction is the single-checkout exclusion. It is not a cost cap. It prevents two steps from switching the same working tree at once (`take_checkout`, `devteam/runner.py:196-223`, checks and then switches with no lock). So it serves the stated outcome rather than limiting it. The third challenge's finding is fixed: the `merged` criterion now waits instead of failing, leaves the branch alone, and turns away branch-role and check steps. It also states that `rejected` runs alongside by choice.

I checked the Analysis against the repository again and it holds. `active` is set and cleared in `invoke` (`runner.py:261-268`) and `verify` (`:295-302`). `run_item` returns False on `Waiting` and True on failure (`:335-347`), which matches the `run_pass` count. `merged` raises `StepFailed` on a dirty checkout and then fast-forwards (`:52-65`). The end-of-step `commit_all` for branch roles is at `:281-282`. The TUI keeps its own copy of the loop and stops everything on an exception (`devteam/tui.py:630-643`). The `active` consumers are at `tui.py:99`, `:662-663` and `:686-687`. Four roles in `config/roles.toml` set `branch = true`, and there is no `max_agents` key. The backlog is a separate repository excluded via `.git/info/exclude` (`devteam/git.py:80-92`). Item edits by parallel agents therefore never reach a branch-role commit, and only stray files in the code checkout can, which is the risk the customer accepted in Question 2.

One wording point, which does not need the customer and does not change what gets built. In the criterion on a running branch-role step, "used only when no step is running" should read "no checkout-using step". If an analyst is running and the checkout sits on another unfinished item's branch, a literal reading would withhold the `take_checkout` holder message without saying what replaces it. The intent, a step turned away by the step lock, is clear from the next criterion. It is worth tightening if the item is reopened, but it does not block the work.

## Feedback

- **answered -> analysis:** The requirement to limit the number of agents is imagined and did not come from the customer. If the customer chooses to work on more stories concurrently, that is their choice.

## Tests

Narrative tests in `tests/test_parallel_cli.py` start the real `dev-team run --once` command against a
product repository with a remote. The engines are the stand-in executable `tests/stubs/rendezvous`, which
finishes a step only once other items' steps have started (else it exits 3), so the run passes only if the
steps genuinely overlap.

- `test_analysts_for_several_stories_work_at_the_same_time`: three stories at analysis, each analyst waits
  for the other two to start; all reach `ready` (criteria 1, 2, 8 in part, 13 in part, and the headless side of 14).
- `test_analysis_runs_alongside_a_branch_step_and_the_other_branch_step_waits_for_the_checkout`: two
  implementer steps and one analyst; the analyst only finishes once a branch step is running, and the
  other branch step reports "waiting for <id>, which is using the checkout" (criteria 4 and 5).

Left to the implementer's unit tests (`tests/test_dispatch.py`, `tests/test_tui.py`): the no-limit check on
four items and `max_agents`, Stop/Start while draining and the stopping title, merged and rejected
exclusion, continuous dispatch with items becoming runnable later, unexpected worker exceptions, `active_ids()`,
atomic run counts, `(item_id, line)` output prefixes, stray-file commits, and the README prose.

Run one on its own: `dev-team check tests.test_parallel_cli`, or a single test as
`dev-team check tests.test_parallel_cli.ParallelAgentsFromTheCommandLine.test_analysts_for_several_stories_work_at_the_same_time`.

## Implementation

Implemented. No criteria or findings are blocked. The latest Feedback rejects an agent cap; none was introduced. No workflow check had run before this implementation.

Changes:

- Runner dispatches independent threads with one reserved step per item and no agent limit. Continuous dispatch polls while workers run; synchronous `run_pass` joins its submissions, and `run(once=True)` drains work and follows progress without looping indefinitely on waits.
- One runner lock guards all reads and writes of failures, waiting reasons, run counts and active ids. Public state readers return copies. A checkout reservation covers the whole branch-role, check or merged step, including transitions and commits. Contending steps wait without counting as completed or failing; rejected actions remain independent.
- Unexpected worker exceptions are reported against their item and mark only that item failed. Retry retains the existing session reset behavior.
- TUI uses the runner dispatcher, prefixes engine output with item ids, marks every running item, names all active ids on Stop and quit, and refreshes the stopping title when workers finish. Stop ends dispatch without joining workers; Start during the drain cannot duplicate them.
- README documents parallel non-branch agents, branch changes during analysis, and the accepted risk of stray parallel files entering a branch-role commit. Existing stream, launcher and TUI tests were adjusted for active ids, item-bound listeners and independent worker failures. The TUI failure fixture now assigns replies per item, avoiding dependence on thread scheduling.

Acceptance-criterion coverage (numbered in the order above):

1. **Unit test:** `tests.test_dispatch.Dispatch.test_two_and_four_agents_start_together_without_duplicate_steps` holds both fake engines on an Event and observes both running before release.
2. **Unit test:** the same test observes all four running and verifies roles configuration contains no `max_agents` key.
3. **Unit tests:** the concurrency test rejects duplicate passes; `tests.test_tui.ParallelAgents.test_tui_dispatches_new_work_during_a_run_and_can_restart_while_draining` exercises Stop/Start with blocked workers and checks one invocation per item.
4. **Unit tests:** `test_branch_and_check_steps_exclude_each_other_but_allow_analysis` checks the exact running-holder reason, an unchanged branch, and parallel analysis. Existing `tests.test_checkout` covers an unfinished branch holder after the running step ends.
5. **Unit test:** the branch/check exclusion test covers branch/branch, branch/check, check/branch and check/check, counts only the two running steps (holder and analyst), and checks no failure is recorded for the waiter.
6. **Unit tests:** `test_merged_waits_for_checkout_and_later_runs_without_switching_early` exercises the real merged action after branch/check workers finish. `test_running_merged_excludes_branch_and_check_but_not_rejected` blocks a wrapper around real merged and verifies converse exclusion and concurrent rejected dispatch. Only the rejected action's external GitHub fetch is replaced in this lock test; existing rejected-action tests cover its behavior.
7. **Unit tests:** `test_continuous_headless_dispatch_starts_new_work_and_stop_does_not_join`, `test_cli_run_dispatches_new_work_while_the_first_engine_is_blocked`, and the ParallelAgents TUI test create or move new work after the first call blocks. The CLI test drives the actual command entry point with real repositories and dispatch, injecting fixture configuration, a fake engine and a stop Event at runner construction. Live external agent processes and terminal interaction remain for the tester's narrative tests.
8. **Unit tests:** `test_expected_and_unexpected_failures_do_not_stop_other_workers` covers ordinary failure, continued work, suppression of retries and explicit retry. Existing runner and TUI retry tests also pass.
9. **Unit tests:** the failure-isolation test covers an unexpected RuntimeError, item-specific reporting, failed state, continued work and completed futures. The reworked TUI output crash test checks failed state while preserving output.
10. **Unit tests:** concurrency tests check sorted active ids and that modifying a returned list changes no runner state. ParallelAgents verifies membership markers and a quit confirmation naming both ids. Launcher assertions now use `active_ids()`. Stop notification text directly joins the same ids; no separate unit test for that plain formatting.
11. **Unit test:** `test_count_run_is_atomic_and_enforces_limit` uses eight concurrent writers and verifies exactly 100 increments and 100 rejected attempts at the limit. Concurrent state and retry paths are exercised throughout the other dispatch tests. Guarded snapshot properties provide the read side; no separate test that merely restates lock plumbing.
12. **Unit tests:** ParallelAgents checks both concurrent output prefixes; updated `tests.test_engines.Streams.test_runner_passes_registered_listener` verifies `(item_id, line)` binding. Existing engine stream tests retain the one-argument engine callback. Existing fake engines accepting no listener parameter verify that an unregistered listener is omitted.
13. **Unit test:** ParallelAgents checks immediate dispatcher termination with agents still running, the stopping title listing ids, no dispatch while stopped, restart during drain without duplicates, and the stopped title after the final worker finishes. Real agent completion and terminal rendering remain for narrative tests.
14. **Unit tests:** `test_once_drains_all_submissions_and_returns_for_waiting_items` verifies synchronous draining and returning for a held checkout; `test_once_dispatches_work_unlocked_by_a_completion_while_another_worker_runs` verifies newly unlocked work before the blocked worker finishes. Existing runner, checkout, merged and request tests verify transition/failure counts and unchanged serial behavior. The CLI and TUI both drive `Runner.run`; that delegation is plain plumbing and needs no additional test.
15. **Unit test:** existing `tests.test_checkout.CheckoutAcceptance.test_uncommitted_changes_prevent_a_switch` verifies the existing uncommitted-changes message. No new wording was added.
16. **Unit test:** `test_parallel_non_branch_file_is_included_in_branch_commit` writes a real stray file while a branch engine is running and verifies it appears in the branch's commit. No end-of-step refusal was added.
17. **No unit test:** README changes are prose; the three documented behaviors can be reviewed directly.
18. **Check:** `dev-team check` passed; this is the project regression check, not an extra unit assertion.

Checks and evidence:

- Direct module tests: `uv run python -m unittest tests.test_dispatch tests.test_tui tests.test_runner tests.test_checkout tests.test_merged tests.test_requests tests.test_engines tests.test_launcher` — **passed, 141 tests**; `backlog/log/STORY-020/final-unit.log`.
- Final concurrency and TUI dispatcher tests, including the subsequently added actual CLI entry-point case: `uv run python -m unittest tests.test_dispatch tests.test_tui.ParallelAgents` — **passed, 12 tests**; `backlog/log/STORY-020/final-parallel-unit.log`.
- `dev-team check` — **passed, 295 tests**; harness-saved output: `backlog/log/check/20261014T141004377569.log`. The additional CLI case passed directly after this check; no production code changed afterwards.
- `uv build --out-dir /tmp/story-020-dist` — **passed**, source distribution and wheel built; `backlog/log/STORY-020/build.log`.
- `git diff --check` — **passed**; `backlog/log/STORY-020/diff-check.log` (empty output). Backlog item diff check also passed: `backlog/log/STORY-020/item-diff-check.log` (empty output). The repository provides no separate linter or type-check target.
- Initial test launch failed because the default uv cache is read-only: `backlog/log/STORY-020/initial-unit.log`. Subsequent commands used `UV_CACHE_DIR=/tmp/story-020-uv-cache` successfully.
- Intermediate dispatch test failures were fixture errors, corrected before the final runs: a supposed human checkout holder was still runnable, and the stray-file test wrote before checkout acquisition rather than during the branch step. Captured failures: `backlog/log/STORY-020/dispatch-unit.log` and `backlog/log/STORY-020/parallel-unit.log`. Initial existing-module passes are in `backlog/log/STORY-020/runner-unit.log` (93 tests) and `backlog/log/STORY-020/tui-unit.log` (37 tests).

## Test run

Run by the harness, 2026-10-14 14:22:46 UTC: passed (exit 0); duration 165.970 seconds.

## Review

Harness run: `backlog/log/STORY-020/verify-20261014T142000562098.log` (298 tests, OK).

Findings, most damaging first:

1. Low: `Runner.dispatch` in `devteam/runner.py` wraps `run_item` in `work()` with no guard around `future.set_result`. `run_item` catches `Exception`, but if its own error reporting (`self.report`, a TUI callback) raises, or a `BaseException` escapes, the future is never resolved and `run_pass` blocks forever on `future.result()`. Fix: in `work()`, use try/except and `future.set_exception` or a default result. Not blocking: it needs a failing report callback, and the criterion's stated cases (an unexpected `Exception` from a step) are handled.
2. Low: `claim` calls `repository.scan()` while holding the runner lock, so every claim and every state read waits on a disk scan. This is a throughput cost, not a correctness one. Scanning before taking the lock would fix it.

No blocking defects found.

Criteria satisfied:

- 1, 2: `claim` and `dispatch` start one thread per runnable item with no cap. Proven by `tests.test_dispatch...test_two_and_four_agents_start_together_without_duplicate_steps`, and by the narrative `test_analysts_for_several_stories_work_at_the_same_time`.
- 3: `claim` rejects ids in `_active`, and `pending()` skips them. Proven by the same dispatch test and by `tests.test_tui.ParallelAgents...can_restart_while_draining`.
- 4, 5: `checkout_user` is set under the lock in `claim`, and the waiter gets "waiting for <id>, which is using the checkout". It is not counted as completed and not marked failed. Proven by `test_branch_and_check_steps_exclude_each_other_but_allow_analysis` and the narrative `test_analysis_runs_alongside_a_branch_step...`.
- 6: `uses_checkout` includes the `merged` action and excludes `rejected`. Proven by `test_merged_waits_for_checkout_and_later_runs_without_switching_early` and `test_running_merged_excludes_branch_and_check_but_not_rejected`.
- 7: `run` polls with a 0.05s wait while steps are in flight, without joining. Proven by `test_continuous_headless_dispatch_starts_new_work_and_stop_does_not_join`, `test_cli_run_dispatches_new_work_while_the_first_engine_is_blocked` and the TUI ParallelAgents test.
- 8, 9: `run_item` catches unexpected exceptions, marks only that item failed, and reports it with the id. Proven by `test_expected_and_unexpected_failures_do_not_stop_other_workers`.
- 10: `active_ids()` returns a sorted copy, and the TUI uses membership, the Stop message and the quit prompt. Proven by the concurrency tests, the ParallelAgents test and the updated launcher test. The recorded reason for no separate Stop-text test (plain string join) is accepted.
- 11: one RLock guards `_failed`, `_waiting`, `_runs` and `_active`. Proven by `test_count_run_is_atomic_and_enforces_limit`.
- 12: the runner binds the item id and the TUI prefixes `id | line`. The engine contract is unchanged and no listener means none is passed. Proven by `tests.test_engines.Streams.test_runner_passes_registered_listener` and the ParallelAgents test.
- 13: Stop ends the loop without joining workers. The title reads "stopping - waiting for <ids>", `on_change` refreshes it, and Start during the drain is allowed. Proven by the ParallelAgents TUI test.
- 14: `run_pass` and `run(once=True)` are synchronous. Proven by `test_once_drains_all_submissions_and_returns_for_waiting_items`, `test_once_dispatches_work_unlocked_by_a_completion_while_another_worker_runs` and the unchanged existing tests. The recorded reason for no test of the CLI/TUI delegation (plumbing) is accepted.
- 15: the existing message is unchanged. Proven by `tests.test_checkout...test_uncommitted_changes_prevent_a_switch`.
- 16: no commit refusal was added. Proven by `test_parallel_non_branch_file_is_included_in_branch_commit`.
- 17: README prose covers parallel non-branch agents, branch changes during analysis, and the stray-file risk. The recorded reason (prose) is accepted, and I read the README diff.
- 18: the harness run above passed.
