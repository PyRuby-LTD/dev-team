---
id: STORY-026
type: story
title: Release the checkout at human steps and try out a waiting story
parent: EPIC-008
workflow: default
step: publish
---
As a customer, I want the checkout released while a story waits for me, and to be able to ask to try out a story that is waiting for me, so that queued stories carry on running while I review, and I can check out and run the one I want to look at as soon as the running step finishes.

## Context

Today `take_checkout` (`devteam/runner.py`) treats any non-terminal item whose `devteam/<id>` branch is checked out as the holder of the checkout, so an item holds it through the human-owned `accept` and `pull-request` steps until it reaches `done`. Every other code-changing item waits on the customer's review.

Decisions:

- An item holds the checkout only while it is at a step that uses it (branch-role, check and `merged` harness steps, as in `Runner.uses_checkout`) or while the customer is trying it out. An item at `accept` or `pull-request` does not hold it, so the next queued story switches to its base branch and starts.
- The customer can ask to try out an item at `accept` or `pull-request` from the TUI. The request queues a claim on the checkout. It is granted as soon as the running checkout step finishes, ahead of any queued step, including between the steps of a story that is part-way through (for example between `test` and the step after it). A step that succeeds has committed its work, but a failed step, or a `sync` that ended in a conflict (STORY-025), leaves the tree dirty; a try-out never discards that (see Assumptions).
- When the claim is granted, the runner switches to the item's branch and starts the product with a new Makefile target (for example `make run`), named in `config/roles.toml` alongside `[check]`. Its output is kept under `backlog/log/<id>/`. A product without the target reports that and releases the claim.
- Choosing any transition on the item, or a release key, stops the product (its whole process group) and releases the checkout. The TUI shows which item is being tried out.
- `init`'s placeholder Makefile and the README describe the new target.

Depends on the dependency gating story and the branch sync story in this epic (STORY-024 and STORY-025): without them, releasing the checkout would start dependent stories from a base that lacks their dependency, and independent stories would land conflicting pull requests.

## Analysis

What exists today, checked against the code:

- `Runner.take_checkout` (`devteam/runner.py`) raises `Waiting` when the checkout is on a `devteam/<id>` branch whose item is not at a terminal step. `accept` and `pull-request` are human steps and not terminal, so the premise holds: a story waiting for the customer blocks every other code-changing story.
- `Runner.uses_checkout` and `Runner.claim` already serialise steps that need the checkout through `checkout_user`, an in-memory single holder. There is no notion of a queued claim, of a customer holding the checkout, or of a process the runner started for the customer.
- `devteam/check.py` runs the check synchronously with `subprocess.run` and writes its log under `backlog/log/<id>/`. Nothing in the harness starts a long-running process or stops a process group.
- `[check]` in `config/roles.toml` is the only place a Makefile target is named. `initialise.PLACEHOLDER` contains only a `regression` target, and `has_regression` only looks for that. The README (Prerequisites, `init`, and the Makefile section) describes only `make regression`.
- The TUI (`devteam/tui.py`) lists an item's transitions in a dialog and has global bindings (`n y g s l t tab r q`). It has no per-item actions other than choosing a transition, and no display of who holds the checkout.
- `invoke` commits a dirty tree only after a step succeeds. A step that fails (`StepFailed`, before the commit) leaves the agent's work uncommitted, and STORY-025 deliberately ends a conflicting `sync` with an uncommitted merge. `take_checkout` refuses to switch away from a dirty tree, so a released branch is clean only after a successful step; a try-out must cope with a dirty tree.

What would change:

- `take_checkout`: an item at a step that does not use the checkout (as `uses_checkout` decides) does not count as holder, so the next story switches to its base branch. An item that later returns to a checkout step (for example `revise` from `accept` to `implement`) switches back to its existing branch as it does today.
- `Runner`: a try-out claim that is granted ahead of queued steps, including between steps of a part-way story. A try-out waits for the one step currently using the checkout and then takes it before any queued step is dispatched.
- `Runner`: start the product with the new target on the item's branch, log under `backlog/log/<id>/`, and stop its whole process group on release.
- `config/roles.toml`, `devteam/check.py` or `devteam/config.py`: name the run target and load it.
- TUI: a way to request a try-out on an item at `accept` or `pull-request`, a release key, and a visible indication of the item being tried out.
- `devteam/initialise.py` placeholder Makefile and the README: describe the new target.

Assumptions, stated rather than asked:

- `[run]` in `config/roles.toml` holds a full command, like `[check]`: `command = ["make", "run"]`. Which keys the TUI uses is the implementer's choice.
- "No such target" is decided before anything is started: when the command is `make <target>`, the product's Makefile is parsed for a declaration of that target (as `initialise.has_regression` does for `regression`). A missing target, a missing Makefile or a program that cannot be started is the "cannot run" case (criterion 8). Once a process has been started, any later exit, successful or not, is the "product exited" case (criterion 10). The two cannot apply to the same attempt.
- Who holds the checkout across a try-out: the interrupted story is defined by state the runner can see: the item whose `devteam/<id>` branch is checked out when the try-out is granted, if that item's current step uses the checkout (as `uses_checkout` decides). It keeps its place. A story whose step has just ended and moved to a human step (for example `review` to `accept`) is not interrupted and gets no priority. A story left at a checkout step with its branch checked out because the agents are stopped counts as interrupted in the same way. While the try-out is claimed or running, no other story's checkout step starts. When the try-out is released, the interrupted story's next step is dispatched before any other queued checkout step and takes the checkout back through the existing `take_checkout` path (switch to base, then to its own branch). Only if no story was interrupted is the checkout simply left on the tried item's branch, where it holds nothing because that item is at `accept` or `pull-request`.
- A dirty checkout when the try-out would be granted (a failed step's uncommitted work, or a `sync` conflict mid-merge): the request keeps waiting, nothing is discarded, and the TUI shows that it is waiting because the working tree has uncommitted changes. It is granted once the tree is clean (for example after the conflict is resolved or the tree is cleaned by the customer). The customer can cancel a waiting request with the release key. This follows the no-discard rule below and is stated as an assumption, not asked.
- A try-out does not depend on the agent loop. If no step is using the checkout it is granted at once, whether agents are running or stopped. If a step is running it is granted when that step ends, including when the agents have been stopped (stopping only ends dispatch). Stopping or starting the agents has no effect on a granted try-out; starting them while one is granted dispatches non-checkout steps as usual and holds checkout steps back until release.
- On release the harness does not clean or discard anything the product wrote. If the tree is not clean afterwards, every checkout step (including `merged`, which fails when the tree is dirty) is held back until the customer cleans it. The customer was not asked about this; it is the safe default. Because it would otherwise surface only as an activity-log line, the TUI tells the customer at release time that the tree has uncommitted changes and that checkout steps will not run until it is clean.
- Quitting the TUI while a product is running stops the product and releases the claim, so no orphaned process is left holding the product's port.
- A try-out is requested only for an item at `accept` or `pull-request`. Requests for items at other steps are refused with a message. Only one try-out can be claimed or running at a time; a request for a second item is refused with a message rather than queued. This is an assumption: the customer's text says only that the request queues behind running steps.
- The claim is held in memory by the TUI's runner. Running `dev-team run` in another terminal during a try-out is not supported and is out of scope; it could switch the branch under the running product.
- Out of scope: the dependency and branch sync behaviour (STORY-024, STORY-025) and removing the `accept` transition (STORY-027).

Existing tests that assert the behaviour this story removes, to be reversed deliberately rather than treated as regressions: `tests/test_runner.py` `test_pr_decision_holds_checkout_until_terminal` and the test in `tests/test_pr_decision.py` asserting that an item at `pull-request` blocks other code changes. `rejected` does not use the checkout (`uses_checkout`), so an item at `rejected` stops holding it too. The item at `merged` still holds it.

Decisions taken in response to the challenge (all engineering choices, none needs the customer):

- `merged` on another story's checkout. Checked at `devteam/runner.py:54-67` and `devteam/git.py:52-69`: `merged` fails with `StepFailed` on a dirty tree, and `git.fast_forward` leaves the checkout on the base branch. Once `pull-request` no longer holds the checkout, `merged` will often find another story's `devteam/<id>` branch checked out. So: (a) a dirty tree makes `merged` wait (`Waiting`, with the reason shown, like `take_checkout` does) instead of failing, but only when the checkout is on another item's `devteam/<id>` branch (or on the base branch, which belongs to no item); a dirty tree on the merged item's own branch still fails with `StepFailed` exactly as today, so `tests/test_merged.py`, `tests/test_merged_cli.py` and the README's account of `merged` (`README.md:204-212`) are unchanged. One story's uncommitted state therefore never puts another story into the failed set; the existing "no base recorded" and "not a git repository" failures stay as they are; (b) after the fast-forward, if the checkout was on another item's `devteam/<id>` branch, `merged` switches back to that branch, so that story is still the interrupted one and keeps its priority; (c) if the checkout was on the base branch, or on the merged item's own branch, it is left on the base branch as today. `merged` still counts as a checkout step: while it runs no other checkout step runs, and a second `merged` waits.
- A story in the runner's failed set, or one that has used its `max_runs`, is never the interrupted story, because its next step would not be dispatched until the customer retries it or restarts, and would hold the whole queue. It gets no priority on release; queued steps proceed in the usual order. If the customer retries it, it is an ordinary queued step again.
- Stopping the product: release sends SIGTERM to the process group, waits up to 5 seconds, then sends SIGKILL to the group. The checkout is treated as free only once the group has exited. The TUI stays responsive while this happens, and shows that the product is stopping.

- A transition the customer did not choose. Any transition applied to the tried item, by whoever applies it (including STORY-023 applying `merged` automatically), stops the product and releases the checkout, as if the customer had chosen it. A pending request for that item is cancelled likewise.

Open risk, not a blocker: the try-out child process has the customer's terminal environment; the story does not ask for its output to be shown in the TUI beyond the log file.

## Acceptance criteria

Updated after the customer’s 2026-10-26 PR feedback: the branch-switch action below replaces the original managed try-out criteria 4–13. Original criterion 14 is now criterion 9. The Context and Analysis above and Challenge below record the earlier investigation; their managed try-out design is superseded.

1. With one story at `accept` or `pull-request` and another queued at a checkout step, the queued story starts without any action by the customer: the checkout is switched to the base branch and then to the queued story's branch.
2. A story at `accept` or `pull-request` is not reported as holding the checkout, and no other story is reported as "waiting for" it. A story at a branch-role or check step, or running `merged`, still holds the checkout while that step runs, and a second such story still waits for it. A `merged` step that finds another story's branch (or the base branch) checked out with uncommitted changes waits with a visible reason, does not fail and does not enter the failed set; once the tree is clean it runs. A `merged` step with uncommitted changes on the merged item's own branch still fails as it does today. After `merged` runs, the checkout is back on the other story's branch if it was on one, so that story keeps its place as the interrupted story; otherwise it is on the base branch as today.
3. A story sent back from `accept` with `revise` returns to `implement` on its existing `devteam/<id>` branch with its earlier commits intact.
4. In the TUI, selecting an item and pressing `x` switches the checkout to its existing `devteam/<id>` branch. This is available at any step with an existing branch, and does not change the item's step or create a branch. Earlier commits remain intact.
5. The customer must stop agent dispatch with `s` before switching. Switching is refused visibly while dispatch is running or any step is still active, including while stopped agents finish their current work. Once those steps finish, the customer can press `x` again to switch.
6. If the checkout has uncommitted tracked or untracked changes, switching is refused visibly, the checkout stays on its current branch, and the work is preserved. The customer can retry after cleaning the tree; the harness does not discard anything.
7. If the selected item's branch does not exist, switching is refused visibly without creating it or changing the current branch.
8. The README describes stopping agents, selecting the item, pressing `x`, and starting and stopping the app in another terminal, including any local services. The harness does not launch, monitor or stop the product, hold a try-out claim, or require `[run]` configuration or a `make run` target. The init placeholder requires only the existing regression target, and an existing Makefile is not rewritten.
9. Existing behaviour is unchanged for products and items that never use the branch-switch action, and the project's regression suite passes, apart from the two tests named in the Analysis, which are deliberately changed to assert that an item at `pull-request` (and at `rejected`) no longer blocks another item's checkout. An item running `merged` still blocks other checkout steps while it runs; the only deliberate changes to `merged` are that a dirty tree on another item's branch or on the base makes it wait instead of fail (a dirty tree on its own branch still fails), and that it returns the checkout to another story's branch when it found one (criterion 2).

## Challenge

Verdict: sound. A competent engineer could implement the item as written, and a reviewer could tell whether they had.

The fourth analysis resolves both findings from the third challenge. Decision (a) now takes option (i): a dirty tree makes `merged` wait only when another item's branch or the base is checked out, and a dirty tree on the merged item's own branch fails as it does today. AC2 and AC14 say the same, so `tests/test_merged.py`, `tests/test_merged_cli.py` and `README.md:204-212` stay as they are. Any transition on the tried item, including STORY-023's automatic `merged`, now releases the try-out (Decisions, AC11). I checked the code claims against the repository again and they hold: `merged` (`devteam/runner.py:54-67`) raises `StepFailed` on a dirty tree, `git.fast_forward` (`devteam/git.py:52-69`) leaves the checkout on the base, `uses_checkout`, `claim` and `take_checkout` are at `runner.py:215`, `219` and `255`, and the two tests to be reversed exist (`tests/test_runner.py:259`, `tests/test_pr_decision.py:204`).

One minor point, which does not change what gets built or how it is judged. The Assumptions bullet on "No such target" calls the cannot-run case "criterion 8" and the product-exited case "criterion 10". In the numbered list those are AC10 and AC12; AC8 is the TUI's request indicator. The bullet describes both cases in words and AC10 refers correctly to AC12, so a reader can still follow it. The analyst should correct the two numbers when next editing the item.

No other findings. Every criterion traces back to the stated outcome: queued stories carry on while the customer reviews, and the customer can try out a waiting story.


## Implementation

Addressed all four findings in the latest Review. The customer's PR feedback remains implemented: `x` switches to an existing story branch after dispatch stops and active steps finish; the customer starts and stops the app separately. No managed try-out, run command or process lifecycle was reintroduced. Changes are left in the working tree for the runner to commit.

- Restored `Backlog.from_agents` to `call_from_thread`, preserving synchronous delivery from agent threads.
- Removed the leftover `finish_quit` helper and restored direct exit after quit confirmation. Existing unmount handling still stops dispatch.
- Restored `Repository.transition` to return within its mutation block.
- Removed the premature run-limit checks before checkout acquisition in `invoke` and `verify`, and restored the limit check inside atomic `count_run`. Added a real-git regression test for exhausted branch-role and check steps: dirty work makes them wait without failure or data loss; after cleanup they switch to their branch and then report the run limit without invoking an agent or check.
- Updated acceptance criteria 4–8 to describe the customer's branch-switch request, replacing original criteria 4–13; original compatibility criterion 14 is now 9. Marked the earlier investigation as historical. The prior launch/shutdown review findings no longer apply to the removed feature.

Acceptance criterion coverage:

1. Unit tests: `tests.test_checkout`, `tests.test_runner` and `tests.test_pr_decision` cover queued stories proceeding after human steps release ownership.
2. Unit tests: `tests.test_dispatch` and `tests.test_merged` cover checkout serialization, foreign/base dirty waiting, own-branch dirty failure and restoring the other story's branch and commits. Existing `tests.test_merged_cli` checks are also rerun as named in review.
3. Unit test: `tests.test_switch_branch.SwitchBranch.test_switches_to_existing_branch_at_human_and_checkout_steps_without_changing_work` covers revision preserving commits.
4. Unit tests: `tests.test_switch_branch` proves existing-branch switching without step changes or branch creation. The existing tester-authored `tests.test_switch_branch_journey` covers selecting a waiting story and pressing `x` in the running TUI; no journey suite was added. Key forwarding is plain plumbing and needs no unit test.
5. Unit tests: `tests.test_switch_branch` proves the dispatch guard and unfinished-step refusal; `tests.test_tui` exercises existing agent start/stop behavior. Visible notification wording is presentation left to human judgement.
6. Unit test: `tests.test_switch_branch.SwitchBranch.test_dirty_tracked_and_untracked_work_is_preserved` proves dirty-work preservation, refusal and retry after cleanup. Notification wording is left to human judgement.
7. Unit test: `tests.test_switch_branch.SwitchBranch.test_missing_branch_is_reported_without_creating_it` proves missing-branch refusal. Notification wording is left to human judgement.
8. No new unit test: README wording and footer presentation are left to human judgement; configuration removal and placeholder literals are plain code. Existing `tests.test_initialise` covers placeholder creation and preserving existing Makefiles. Product startup/shutdown belongs to the customer and needs no harness journey test.
9. Existing relevant module tests are rerun directly. `tests.test_dispatch.Dispatch.test_exhausted_checkout_steps_wait_for_dirty_work_before_enforcing_limit` protects restored run-limit ordering; the existing atomic-count test remains. Thread callback, quit and transition reversions are plumbing covered by existing TUI/backlog tests, so no tests merely restate those calls. The full suite is left to the runner as instructed.

Checks and evidence (paths relative to the repository):

- Read `backlog/log/STORY-026/verify-20261026T195534186794.log`: prior full run passed 359 tests; this predates these review fixes.
- `.venv/bin/python -m unittest tests.test_dispatch.Dispatch.test_exhausted_checkout_steps_wait_for_dirty_work_before_enforcing_limit`: passed, 1 test; `backlog/log/STORY-026/review-run-limit.log`.
- `UV_CACHE_DIR=/tmp/devteam-uv-cache uv build`: passed, source distribution and wheel; `backlog/log/STORY-026/review-build.log`.
- `.venv/bin/python -m unittest tests.test_switch_branch_journey`: passed, 1 existing tester-authored journey test rerun because review names it; `backlog/log/STORY-026/review-switch-journey.log`.
- `.venv/bin/python -m unittest tests.test_switch_branch tests.test_tui tests.test_runner tests.test_dispatch tests.test_checkout tests.test_merged tests.test_merged_cli tests.test_pr_decision tests.test_initialise tests.test_backlog tests.test_backlog_writes tests.test_check`: passed, 153 tests, exit 0; `backlog/log/STORY-026/review-modules.log`. This includes the modified modules and retained tests named in review.
- `git diff --check` in the product and backlog working trees: passed; `backlog/log/STORY-026/review-diff-check.log`.
- No separate linter or type checker is configured. No full suite was run during implementation. No check failed.

## Tests

Journey test: `tests.test_switch_branch_journey.SwitchBranchJourney.test_customer_switches_to_the_branch_of_a_story_waiting_for_review` (`tests/test_switch_branch_journey.py`). It drives the real TUI over the checkout fixture: one story waits at `accept` with its branch, another is queued, agents are stopped. The customer selects the waiting story and presses `x`; the checkout is on its `devteam/<id>` branch at the same commit and the story is still at `accept`. It replaces the removed try-out journey, which tested superseded behaviour.

Left to unit tests: refusal while steps run or the tree is dirty, a missing branch, revision keeping commits (`tests.test_switch_branch`); human-step checkout release and `merged` waiting and restoring (`tests.test_checkout`, `tests.test_dispatch`, `tests.test_merged`, `tests.test_pr_decision`). The current acceptance criteria reflect the PR feedback; the original managed try-out criteria have been replaced.

Left to human judgement as presentation: notification wording, the footer label for `x`, and the README text.

Run the journey on its own with `dev-team check tests.test_switch_branch_journey`.

## Test run

Run by the harness, 2026-10-26 20:26:49 UTC: passed (exit 0); duration 177.560 seconds.

## Review

Verdict: approve. The four findings from the earlier review are resolved in the diff: `from_agents` is back on `call_from_thread`, `finish_quit` is gone, `Repository.transition` is unchanged, and `check_run_limit` no longer runs before `take_checkout`. The product diff is now `devteam/runner.py`, `devteam/tui.py`, the README and tests. The harness run (`backlog/log/STORY-026/verify-20261026T200548517346.log`) passed all 360 tests.

No defects found. One cosmetic note: the new `from .runner import ...` line in `devteam/tui.py` is out of alphabetical order. It is not worth a revision.

Criteria and proof:

- 1: `tests.test_checkout`, `tests.test_runner`, `tests.test_pr_decision`. `take_checkout` uses `checkout_holder`, which counts only steps that use the checkout. Satisfied.
- 2: `tests.test_dispatch` and `tests.test_merged` cover serialisation, foreign or base dirty waiting, own-branch dirty failing, and restoring the other story's branch (`merged` in `devteam/runner.py`). Satisfied.
- 3: `tests.test_switch_branch` `test_switches_to_existing_branch_at_human_and_checkout_steps_without_changing_work`. Satisfied.
- 4: `tests.test_switch_branch` and the journey `tests.test_switch_branch_journey` (the `x` key in the real TUI). Satisfied.
- 5: `test_running_step_must_finish_before_switching` and `test_tui_requires_dispatch_to_be_stopped_even_between_steps`. Satisfied. Notification wording is presentation; I accept the recorded reason.
- 6: `test_dirty_tracked_and_untracked_work_is_preserved`. Satisfied.
- 7: `test_missing_branch_is_reported_without_creating_it`. Satisfied.
- 8: README prose and the footer label are presentation; I accept the recorded reason. No `[run]` config or run target remains in the diff, and `tests.test_initialise` covers keeping an existing Makefile.
- 9: the full suite passes. The two named tests were reversed deliberately. `tests.test_dispatch` covers the restored run-limit ordering.

## Pull request

https://github.com/PyRuby-LTD/dev-team/pull/22

## Pull request feedback

**Review (COMMENTED)** by tarttelin (2026-10-26T19:47:59Z):
> As a user, I want to be able to test the code on a branch. I can do that by hitting 's' to stop agents once they finish what they are doing, then switch to the branch associated with the story I want to test. To make it easier, I just want an easy way of having selected a story, to switch to that stories branch from within dev-team tui. Once the code is there, I can then open another terminal window and start the app myself, including any stubs or DBs associated with the local test environment. There is a good chance that 'make run' will be insufficient so we shouldn't include it as a pre-req

**Inline comment** by tarttelin on config/roles.toml line 46 (2026-10-26T19:39:56Z):
> remove make run 

**Inline comment** by tarttelin on devteam/tryout.py (2026-10-26T19:40:47Z):
> This is overkill. Remove tryout as a concept.

**Inline comment** by tarttelin on devteam/tui.py line 396 (2026-10-26T19:42:16Z):
> The behaviour should be switch to this branch so the user can try out the app. The user can handle starting it up and deciding when to shut it down.

**Conversation comment** by tarttelin (2026-10-26T19:46:41Z):
> As a user, I want to be able to test the code on a branch. I can do that by hitting 's' to stop agents once they finish what they are doing, then switch to the branch associated with the story I want to test. To make it easier, I just want an easy way of having selected a story, to switch to that stories branch from within dev-team tui. Once the code is there, I can then open another terminal window and start the app myself, including any stubs or DBs associated with the local test environment. There is a good chance that 'make run' will be insufficient so we shouldn't include it as a pre-req
