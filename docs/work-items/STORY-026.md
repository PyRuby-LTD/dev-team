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

1. With one story at `accept` or `pull-request` and another queued at a checkout step, the queued story starts without any action by the customer: the checkout is switched to the base branch and then to the queued story's branch.
2. A story at `accept` or `pull-request` is not reported as holding the checkout, and no other story is reported as "waiting for" it. A story at a branch-role or check step, or running `merged`, still holds the checkout while that step runs, and a second such story still waits for it. A `merged` step that finds another story's branch (or the base branch) checked out with uncommitted changes waits with a visible reason, does not fail and does not enter the failed set; once the tree is clean it runs. A `merged` step with uncommitted changes on the merged item's own branch still fails as it does today. After `merged` runs, the checkout is back on the other story's branch if it was on one, so that story keeps its place as the interrupted story; otherwise it is on the base branch as today.
3. A story sent back from `accept` with `revise` returns to `implement` on its existing `devteam/<id>` branch with its earlier commits intact.
4. In the TUI the customer can request a try-out on an item at `accept` or `pull-request`. Requesting it on an item at any other step, or on a second item while one is claimed or being tried out, is refused with a visible message and changes nothing.
5. A requested try-out does not interrupt the step currently using the checkout. It is granted as soon as that step ends, before any other queued checkout step starts, including when the running story still has later steps (for example after `test`, before its next step). If the tree is clean at that point the try-out is granted; if it is dirty (a failed step's uncommitted work, or a conflicting `sync`), the request stays waiting, the TUI shows that it is waiting because of uncommitted changes, nothing is discarded, and it is granted once the tree is clean. The release key cancels a waiting request.
6. With story A part-way (a step has just ended successfully and its next step still uses the checkout) and story B queued at a checkout step, a try-out of a third item C is granted before A's next step starts. After release, A's next step runs before B's first checkout step, on A's own `devteam/<A>` branch with its earlier commits intact. While the try-out is claimed or running, B does not start. If A is in the runner's failed set (its last step failed) or has used up its allowed steps, it is not the interrupted story: on release, B's queued step runs in the usual order and the queue is not held for A until the customer retries it. If `merged` for some other story ran between A's steps, A is still the interrupted story and still runs first on release.
7. A try-out requested while nothing is using the checkout is granted at once, with the agents stopped as well as running. Stopping the agents while a try-out is requested still lets it be granted when the running step ends; stopping or starting the agents while a try-out is running does not stop the product. If a story was left at a checkout step with its branch checked out because the agents are stopped, it is the interrupted story and its next step runs first on release, as in criterion 6.
8. The TUI shows while a try-out is requested but not yet granted, and which item is being tried out once it is granted.
9. When granted, the checkout is on the tried item's `devteam/<id>` branch and the command configured in `[run]` in `config/roles.toml` (`make run` by default) is running in the checkout. Its output is written under `backlog/log/<id>/`.
10. If the configured command cannot run because the Makefile or its target is missing, or the program cannot be started, the customer is told so in the TUI, no product is started, and the claim is released so queued steps proceed. A product that was started and then exits is not this case (criterion 12).
11. Any transition on the tried item (chosen by the customer or applied automatically, such as `merged` by STORY-023), or pressing the release key, stops the product and every process it started (the whole process group) and frees the checkout; quitting the TUI does the same. A product that ignores a polite stop request is forced to stop after a short grace period (5 seconds), so no process of the product survives release, and the TUI stays responsive meanwhile. If the tree is clean, queued steps then start. If the product left uncommitted or untracked files, the TUI says so at release time and checkout steps wait until the tree is clean; nothing is discarded by the harness.
12. If the product exits by itself after starting, the customer is told and the checkout stays claimed until released by one of the actions in criterion 11, so the customer's inspection is not interrupted.
13. `devteam init`'s placeholder Makefile contains the run target, and the README documents it alongside `make regression`, including that the harness starts it for the customer and stops it on release. An existing Makefile without the target is not rewritten.
14. Existing behaviour is unchanged for products and items that never request a try-out, and the project's regression suite passes, apart from the two tests named in the Analysis, which are deliberately changed to assert that an item at `pull-request` (and at `rejected`) no longer blocks another item's checkout. An item running `merged` still blocks other checkout steps while it runs; the only deliberate changes to `merged` are that a dirty tree on another item's branch or on the base makes it wait instead of fail (a dirty tree on its own branch still fails, so the `merged` tests and README passage stay as they are), and that it returns the checkout to another story's branch when it found one (criterion 2).

## Challenge

Verdict: sound. A competent engineer could implement the item as written, and a reviewer could tell whether they had.

The fourth analysis resolves both findings from the third challenge. Decision (a) now takes option (i): a dirty tree makes `merged` wait only when another item's branch or the base is checked out, and a dirty tree on the merged item's own branch fails as it does today. AC2 and AC14 say the same, so `tests/test_merged.py`, `tests/test_merged_cli.py` and `README.md:204-212` stay as they are. Any transition on the tried item, including STORY-023's automatic `merged`, now releases the try-out (Decisions, AC11). I checked the code claims against the repository again and they hold: `merged` (`devteam/runner.py:54-67`) raises `StepFailed` on a dirty tree, `git.fast_forward` (`devteam/git.py:52-69`) leaves the checkout on the base, `uses_checkout`, `claim` and `take_checkout` are at `runner.py:215`, `219` and `255`, and the two tests to be reversed exist (`tests/test_runner.py:259`, `tests/test_pr_decision.py:204`).

One minor point, which does not change what gets built or how it is judged. The Assumptions bullet on "No such target" calls the cannot-run case "criterion 8" and the product-exited case "criterion 10". In the numbered list those are AC10 and AC12; AC8 is the TUI's request indicator. The bullet describes both cases in words and AC10 refers correctly to AC12, so a reader can still follow it. The analyst should correct the two numbers when next editing the item.

No other findings. Every criterion traces back to the stated outcome: queued stories carry on while the customer reviews, and the customer can try out a waiting story.


## Implementation

Implemented. Changes remain in the working tree for the runner to commit.

The existing implementation releases human-step checkout ownership, preserves revision branches, prioritises customer try-outs and interrupted stories, waits for dirty work, starts the configured product with evidence logs, and stops its process group asynchronously on release or transition. It includes TUI request/release/status controls, the documented run target and init placeholder, and the specified foreign-branch `merged` behavior.

Addressed both blocking review findings:

- `Tryout.tick` now catches `StepFailed`, reports the checkout problem through `cannot_run`, and releases the claim. Detached HEAD and missing recorded base tests use real git checkouts and prove queued work can proceed after the checkout is repaired. It catches `Waiting` separately, retains the pending claim and shows the reason; a test introduces real uncommitted work between preflight and `take_checkout`, then verifies the product starts after cleanup.
- Added TUI tests for both the `q` action and unmount during a real running try-out. They wait for the parent and forked child to start, then assert the whole process group has gone and the claim is released. The quit case makes both processes ignore SIGTERM, exercising the async quit wait through the five-second forced-stop grace period. No additional journey suite was built.
- Review finding 3 explicitly accepts the existing AC7 agent-toggle plumbing; no further change is needed.

Acceptance criterion coverage:

1. Unit tests: `tests.test_checkout` proves queued work starts from the base after human steps release ownership; `tests.test_runner` checks accept/pull-request/rejected ownership. The existing `tests.test_pr_decision` CLI assertion checks release.
2. Unit tests: `tests.test_dispatch` covers checkout-step serialization; `tests.test_merged` covers dirty foreign/base waiting, own/unrelated dirty failures, and branch restoration. Existing own-branch and CLI merged tests remain unchanged.
3. Unit test: `tests.test_tryout.Tryout.test_stopped_story_keeps_priority_and_revision_keeps_earlier_commits` proves revision preserves the earlier branch commits.
4. Unit tests: `tests.test_tryout` proves refused requests preserve the claim. Key binding and notification forwarding are plumbing with no separate unit test. Selecting and requesting through the running TUI is covered by the tester's existing `tests.test_tryout_journey`. Message presentation is left to human judgement.
5. Unit tests: `tests.test_tryout` covers active-step completion before grant, priority, dirty-work preservation, clean-tree retry and cancellation. The new grant-race test also proves `Waiting` from `take_checkout` retains the request and reason. Existing `tests.test_sync` covers real sync conflicts using the same clean-tree check. Release-key forwarding needs no separate plumbing test.
6. Unit tests: `tests.test_tryout` covers interrupted-story priority, preserved commits, queued-story exclusion and failed/exhausted exclusions; `tests.test_merged` covers priority after foreign merged restores the interrupted branch.
7. Unit tests: `tests.test_tryout` covers granting without an agent loop, preserving a stopped story's place, granting at worker completion and allowing non-checkout work. Start/stop only controls dispatch and does not touch the claim; no separate unit test for that plumbing, as accepted in review. Customer start/stop interaction is left to the tester's journey tests.
8. No presentation test: request/running/stopping/exit/dirty lifecycle is unit tested; status placement and wording are left to human judgement.
9. Unit tests: `tests.test_tryout` launches real commands on the item's branch and checks product output in the item evidence directory. Configuration loading is plain plumbing with no separate unit test. The existing tester journey also exercises the default Makefile command.
10. Unit tests: `tests.test_tryout` covers missing Makefile, missing target and missing executable releasing the claim, then queued work proceeding. New real-git tests cover detached HEAD and missing branch base without a stuck claim. Notification presentation is left to human judgement.
11. Unit tests: `tests.test_tryout` covers transition cancellation/release, nonblocking shutdown, forced kill, descendants, exited parents with living children and preserved dirty output gating checkout work; `tests.test_merged` covers automatic transition shutdown and dirty-release gating. New `tests.test_tui.TryoutShutdown` tests prove quit and unmount await shutdown of the whole group and release the claim. The tester's existing journey covers the release key. No additional plumbing or presentation tests.
12. Unit tests: `tests.test_tryout` proves successful and nonzero product exits keep the claim until release and differ from launch failure. Message wording is left to human judgement.
13. No new unit test for literal placeholder or README prose; those are plain code/presentation, left to human judgement. Existing `tests.test_initialise` covers creation, parsing and preserving existing Makefiles.
14. Compatibility remains covered by existing module tests and the tester's passing full regression run. The full suite is not rerun in this implementation step; no new unit test restates compatibility as a whole. Previously superseded human-step ownership assertions remain deliberately updated.

Checks and evidence (paths relative to the repository):

- Read the latest workflow check, `backlog/log/STORY-026/verify-20261025T214110708066.log`: the prior full regression run passed, 369 tests. This predates the review fixes.
- `.venv/bin/python -m unittest tests.test_tryout tests.test_tui.TryoutShutdown`: passed, 17 tests; `backlog/log/STORY-026/review-focused.log`.
- `.venv/bin/python -m unittest tests.test_tryout tests.test_tui tests.test_runner tests.test_dispatch tests.test_tryout_journey`: passed, 84 tests; `backlog/log/STORY-026/review-modules.log`. This reruns changed modules, runner/dispatcher collaborators, and the existing journey named by the review.
- `UV_CACHE_DIR=/tmp/devteam-uv-cache uv build`: passed, source distribution and wheel; `backlog/log/STORY-026/review-build.log`.
- `git diff --check`: passed; `backlog/log/STORY-026/review-diff-check.log`.
- No separate lint or type-check command is defined by the project. Unit tests were invoked directly; no full `dev-team check` was run. Earlier implementation evidence remains under `backlog/log/STORY-026/`.

## Tests

Journey test: `tests.test_tryout_journey.TryoutJourney.test_customer_tries_out_a_story_waiting_for_review_and_releases_it` (`tests/test_tryout_journey.py`). It drives the real TUI: with one story waiting at `accept` and another queued at a checkout step, the customer selects the waiting story and presses `x`; the product's own Makefile `run` target (the default `[run]` command) starts on `devteam/<id>`, its output appears under `backlog/log/<id>/`, and the story stays at `accept`. Pressing `e` stops the product process, and the queued story then starts on its own. This extends the existing checkout fixture rather than adding new canned data.

Left to the implementer's unit tests: criteria 1 to 3, 5 to 7, 9 to 12 and 14 (`tests.test_tryout`, `tests.test_checkout`, `tests.test_dispatch`, `tests.test_merged`, `tests.test_runner`, `tests.test_pr_decision`), including refusals, dirty-tree waiting, priority, forced shutdown and quit handling.

Left to human judgement as presentation: criterion 8 (status and notification wording and placement), the wording of the criterion 4 and 10 messages, and the placeholder Makefile and README text of criterion 13.

Quitting the TUI during a running try-out (criterion 11) is covered by the implementer's `tests.test_tui.TryoutShutdown`, which uses a real running product, so the journey was not extended for it.

Run the journey on its own with `dev-team check tests.test_tryout_journey`.

Full suite after the review fixes: passed, 373 tests (`backlog/log/check/20261025T214736912353.log`).

## Test run

Run by the harness, 2026-10-25 21:53:46 UTC: passed (exit 0); duration 183.467 seconds.

## Review

Verdict: approve. The harness run (`backlog/log/STORY-026/verify-20261025T215043145160.log`) passed all 373 tests. Both blocking findings from the earlier review are fixed in the diff.

Findings: none blocking.

- Earlier finding 1 (`Tryout.tick` letting `StepFailed` and `Waiting` escape) is fixed. `devteam/tryout.py` now catches `Waiting` separately, keeping the claim and showing the reason. It routes `StepFailed` and the other launch errors through `cannot_run`, which releases the claim. Real-git tests cover detached HEAD, a missing recorded base, and a tree dirtied between preflight and `take_checkout`.
- Earlier finding 2 (quit during a try-out unproven) is fixed. `tests.test_tui.TryoutShutdown` quits and unmounts with a real parent and child process, including SIGTERM-ignoring processes, and asserts the group has gone and the claim is released.
- Minor, not blocking: `Backlog.call_from_thread` was swapped for `call_later` in the agent-callback path. The suite passes with it, but no criterion asks for the change. Worth a second look if the TUI shows odd updates from worker threads.

Criteria, each with its proof:

- 1: `take_checkout` and `checkout_holder` use `uses_checkout`. Proven by `tests.test_checkout`.
- 2: `merged` waits on a dirty foreign or base checkout, fails on its own dirty branch, and restores the other story's branch. `claim` still serialises checkout steps. Proven by `tests.test_merged` and `tests.test_dispatch`.
- 3: `tests.test_tryout` `test_stopped_story_keeps_priority_and_revision_keeps_earlier_commits`.
- 4: refusals in `Tryout.request`, proven by `tests.test_tryout`. The `x` binding is exercised by `tests.test_tryout_journey`. Message wording is presentation; accepted.
- 5, 6: `checkout_priority`, the `tick` call from the worker `finally`, and the `pending` ordering. Proven by `tests.test_tryout` (preempt, dirty wait, cancel, failed or exhausted exclusion) and `tests.test_merged` (priority after a foreign `merged`).
- 7: `tests.test_tryout` covers granting with agents stopped and running. The recorded reason for no direct start/stop test is that the toggle never touches `Tryout`. I accept it, since `action_toggle_agents` does not reference the claim.
- 8: presentation (status line `#tryout-status` and notifications). I accept the recorded reason.
- 9: `tests.test_tryout` and the journey `tests.test_tryout_journey`. Config loading is plumbing.
- 10: `tests.test_tryout` covers a missing Makefile, a missing target, a missing program, detached HEAD and a missing base. Each releases the claim and queued work proceeds.
- 11: `tests.test_tryout` (release, forced kill, descendants, dirty release), `tests.test_merged` (automatic transition), `tests.test_tui.TryoutShutdown` (quit and unmount), and the journey for the release key.
- 12: `tests.test_tryout` `test_make_target_and_nonzero_exit_are_a_started_product`.
- 13: placeholder and README prose. I accept the recorded presentation reason; `tests.test_initialise` covers preserving an existing Makefile.
- 14: the full suite passes, and only the two named tests were reversed.
