---
id: STORY-010
type: story
title: Hold a published item for the customer's PR decision
parent: EPIC-003
workflow: default
step: publish
---
As the customer, I want a published item to wait for my pull request decision, so that it is not shown as done before I have reviewed the PR.

## Analysis

### What exists today

- `workflows/default.json`: `accept` has transition `pr` -> `publish` (owner `agent:publisher`). `publish` has the single transition `published` -> `done`, so an item shows as done the moment the PR is opened. `accept` -> `done` is the separate no-PR path.
- `devteam/workflow.py`: `build()` accepts owners `human`, `agent:<role>` and `check` only. `Step` has `role`, `human`, `check` and `terminal` properties. A `check` step must have exactly the transitions `passed` and `failed`.
- `devteam/runner.py`: `pending()` picks up only steps with `step.role or step.check`; `run_item()` dispatches to `verify()` for check steps and `invoke()` otherwise. A failing step is recorded in `self.failed`, left in place and not retried until restart.
- `devteam/tui.py`: `owner_label()` and `chosen()` special-case `check` ("checks"); anything else non-human is shown as an agent role. The checkout is held by an item until it reaches a terminal step (`take_checkout`), so a human-owned step after `publish` keeps the branch held, which is wanted while the PR is undecided.
- README documents the default workflow in a table (the `publish` row and the sentence "Merging is yours to do").
- Sibling stories fix the intended shape: STORY-011 gives `merged` the real behaviour (fetch and fast-forward the base, end at a terminal step, fail leaving the item at `merged`), and STORY-012 gives `rejected` its behaviour (copy PR comments into the item, move to `implement`, stay at `rejected` on `gh` failure). STORY-010 is therefore the workflow and engine scaffolding only; no git or `gh` behaviour belongs here.

### What would change

1. `workflows/default.json`: `publish` transitions `published` -> new human step `pull-request`. `pull-request` is owned by `human` with transitions `merged` -> `merged` and `rejected` -> `rejected`. Two new steps, `merged` and `rejected`, use the new harness-owned owner kind.
2. `devteam/workflow.py`: a new owner kind (proposed spelling `harness:<action>`, e.g. `harness:merged`) with a `Step.harness` property and an `action` accessor. The set of known actions (`merged`, `rejected`) is a constant in `workflow.py`, beside `CHECK`, so `build()` validates against it without importing the runner; the runner's registry must have exactly those keys (a test asserts this). Validation: the action name must be in that set, and a harness step has exactly the transition `completed` (mirroring how `check` is constrained to `passed`/`failed`).
3. `devteam/runner.py`: `pending()` includes harness steps; `run_item()` dispatches them through a small registry of action name -> function. Exceptions are handled by the existing `StepFailed` path (item stays, not retried until restart). This story does not take the checkout or count a run for harness steps: the placeholder actions need neither, and STORY-011 decides how a dirty checkout fails (`take_checkout` would raise `Waiting`, which is not what it wants).
4. `devteam/tui.py`: `owner_label()` gives harness steps a label (not a role name) and Moving into `merged` opens no note dialog; moving into `rejected` still opens the note dialog, so the customer can give a reason by hand (saved as feedback on the item). The dialog wording must not name an agent role.
5. `README.md`: update the workflow table and the Branches paragraph.
6. Tests in `tests/test_workflow.py` and `tests/test_runner.py`.

### Assumptions (stated, not questions)

- Step names: `pull-request` (human), `merged` and `rejected` (harness). Transition names out of `pull-request` are `merged` and `rejected`, as the item says.
- Customer decision (question 1): a PR waiting for review holds everything else. The existing release rule (keyed on `terminal`) already does this, so no change to `take_checkout`; criterion 11 pins it with a test.
- Customer decision (question 2): STORY-010 may be released without STORY-012. After STORY-012 the note dialog stays on the move to `rejected`, so the customer can always add their own note when moving to a non-terminal step. The move into `merged` opens no dialog, as it leads only to `done` and there is nothing to tell an agent.
- Until STORY-011 and STORY-012 land, the two actions are placeholders with no side effects: `merged` returns `completed` and its step goes to `done`; `rejected` returns `completed` and its step goes to `implement`. This keeps items from being stranded in the interim; the later stories replace the bodies. Nothing here touches git, `gh` or the PR.
- `publish` is unchanged apart from its target; the publisher prompt and role still do not merge or close the PR.
- Existing items sitting at `publish` or `done` are unaffected; no migration.

### Risk

- Moving an item to `merged`/`rejected` by hand in the placeholder state will advance it without the PR state having been verified. That is acceptable because the customer's decision is the trigger, and the item states the tool does not check GitHub.

## Acceptance criteria

This list is the one to judge. It supersedes the original five criteria (publish no longer reaches `done`; `accept` -> `done` unchanged; workflow validates; the tool never merges or closes the PR; `merged`/`rejected` are harness-owned), all of which it covers.

1. In `workflows/default.json`, `publish` has the single transition `published` -> `pull-request`, and no step reachable from `publish` is `done` without passing through `pull-request`.
2. `pull-request` is owned by `human` and has exactly the transitions `merged` (to step `merged`) and `rejected` (to step `rejected`).
3. `accept` still has `accept` -> `done`, `pr` -> `publish` and `revise` -> `implement`, unchanged from today.
4. Steps `merged` and `rejected` have a harness-owned owner (`harness:merged`, `harness:rejected`), each with exactly the transition `completed`; `merged` -> `done`, `rejected` -> `implement`.
5. `workflow.load("default")` succeeds and `uv run python -m devteam backlog validate` reports no errors; a unit test loads the default workflow.
6. Workflow validation rejects: a harness step whose action is unknown, and a harness step whose transitions are not exactly `completed`. Each has a test naming the step in the error.
7. `Runner.pending()` returns an item at a harness step, and `run_pass()` runs it without any engine call (a test with a stub engine asserts it was never invoked), moves the item along `completed`, and reports the move.
8. If a harness action raises `StepFailed`, the item stays at its step and is not retried until `retry()`/restart, as for other failures (test).
9. The publisher prompt, role and `devteam` code contain no occurrence of `gh pr merge` or `gh pr close`, except where `prompts/publish.md` or `roles/publisher.md` already tell the publisher not to use them (grep over the diff and those two files).
10. The TUI shows harness steps with a non-role label; moving into `merged` opens no note dialog and moving into `rejected` opens one whose text is saved as feedback (tests in `tests/test_tui.py`).
11. An item at `pull-request` is shown as needing the customer (`needs_you`), and it keeps holding the checkout: while it sits there, `take_checkout` for another code-changing item raises `Waiting` (test in `tests/test_runner.py`). `take_checkout` itself is not changed. The checkout is released only when the item reaches a terminal step.
12. `README.md` workflow table lists `pull-request`, `merged` and `rejected` and the `publish` row shows `published` leading to `pull-request`.
13. Neither harness action takes the checkout or counts a run; each only returns `completed`.
14. `uv run python -m devteam check` passes.

## Challenge

Outcome: sound. A competent engineer could build this as written and a reviewer could judge it against the fourteen criteria. The six findings of the earlier challenge are all dealt with: the two that needed the customer are answered under Questions, and the answers are reflected in criteria 10, 11 and 13. The statements under "What exists today" were checked again against `workflows/default.json`, `devteam/workflow.py`, `devteam/runner.py`, `devteam/tui.py` and `README.md` and are accurate. Each criterion traces to REQUEST-002 or to one of the customer's two answers.

The following do not change what is built or how it is judged. They are recorded so nobody is surprised later.

1. **"No note dialog on `merged`" is the analyst's reading, not the customer's words.** The customer's answer 2 says "always be able to add a note when transitioning to a non-terminal step", and `merged` is a non-terminal step (it has `completed` -> `done`). Read literally that contradicts criterion 10. The analyst's reading is the defensible one: today `chosen()` in `devteam/tui.py` opens the dialog only when the next owner is an agent (moves to `YOU`, `finished` and `checks` skip it), so the customer's "always" already describes notes for an agent, and nothing reads a note left on `merged`. If the customer did mean it literally the cost is one condition in `chosen()` and half of criterion 10. Not worth another round; the customer can say so when deciding to play.

2. **The rule that separates the two harness steps in the TUI is left to the engineer.** `chosen()` decides on the target's owner label alone, and both targets are harness-owned, so the engineer must invent the distinction (a label per action, or "every transition leads to a terminal step"). Criterion 10 pins the observable result for the default workflow, which is enough to review against. The engineer should state the rule chosen in the implementation notes, since STORY-011 and STORY-012 inherit it.

3. **Dialog wording at a harness step has no criterion.** The `Note` dialog says "the <owner> takes over" and "Anything the <owner> should know or change?", and `Actions` offers "Leave a note for the <owner>" for any non-human, non-check step. With a harness label these read oddly, and the note on `rejected` is really for the implementer. The analysis says the wording "must not name an agent role"; criterion 10 only requires "a non-role label". An item sits at a harness step only when the runner is stopped (or, after STORY-011/012, when the action failed), so this is cosmetic here.

4. **Re-publishing after a rejection is reachable from this story on and is STORY-013's to fix.** After `rejected` -> `implement` -> ... -> `accept` -> `pr`, `prompts/publish.md` tells the publisher to run `gh pr create` against a branch whose PR is already open. The runner has already pushed the branch (`push = true` in `config/roles.toml`), so the PR is updated; the publisher then has to cope with `gh` refusing to create a second one. The customer's "can be released independently" was given to a question about STORY-012, not STORY-013. Nothing to build here, but the Risk section should not be read as covering it.

5. **Small leftovers.** The exception clause in criterion 9 is vacuous: neither `prompts/publish.md` nor `roles/publisher.md` contains `gh pr merge` or `gh pr close` today (they say "Do not merge the pull request"), so the criterion is simply "no occurrence". "What would change" promises a test that the runner's registry has exactly the known actions, and a README Branches paragraph update; neither has a criterion. Both are cheap and a reviewer can ask for them.

Cheapest way to be wrong: finding 1. One sentence to the customer settles it ("Moving a PR to merged asks for no note, because nothing reads it; is that right?"), and getting it wrong costs one line.

## Challenge response

1. No longer assumed; asked as question 1. Criterion 11 no longer asserts holding.
2. Chose (b): the note dialog stays on the `rejected` move (criterion 10). Whether STORY-010 may ship before STORY-012, and whether to keep the note after it, is question 2.
3. Checkout-taking and run counting dropped (criterion 13).
4. The known actions are a constant in `workflow.py`; the runner's registry is tested against it (What would change, 2 and 3).
5. The revised list is stated to supersede the original.
6. Criterion 9 limited to the two named commands.

## Questions

1. While a pull request is waiting for your review, should other items be able to change code, or should everything wait until you have merged or rejected?

   **Answer:** For now, a PR has to wait for me to review before anything else can run
2. Until STORY-012 lands, rejecting a PR sends the item back to implement with only a note you type by hand. Is that acceptable, or should STORY-010 not be released before STORY-012? Once STORY-012 copies the PR comments in, do you still want the option of adding your own note when you reject?

   **Answer:** Story-010 can be released independently. I can add the PR comments in at the comment prompt when moving step. I still want to be able to add a note after STORY-012 lands as it feels consistent to always be able to add a note when transitioning to a non-terminal step.

## Implementation

Implemented the stated workflow and harness scaffolding. Publishing now moves to the human-owned `pull-request` step; its merged/rejected decisions lead to validated `harness:merged` and `harness:rejected` steps with only `completed` outcomes. The separate `accept` -> `done` path is unchanged.

Added `Step.harness` and `Step.action`, known-action validation, and runner dispatch through an action registry. Both placeholder functions only return `completed`: they do not take the checkout, count a run, invoke an engine, or interact with git, GitHub or the PR. Harness failures use the existing failure/retry handling. `take_checkout` is unchanged.

The TUI labels harness steps `harness`. The note-dialog rule checks the target's harness action: `merged` skips the dialog; `rejected` retains it and saves the customer's text as Feedback. Harness note wording names no agent role. README documents all three new steps and the PR decision's checkout hold, including the placeholder limitation pending STORY-011 and STORY-012.

Added focused tests for invalid harness definitions, default workflow routing, registry agreement, dispatch without engines/checkout/run counting, failure suppression and retry/restart, human attention and checkout holding until terminal, and both TUI decision paths with rejection feedback. No acceptance automation suite was added.

### Checks and actual output

The first direct unit-test invocation could not start with uv's default cache (exit 2):

```text
error: failed to open file `/home/tarttelin/.cache/uv/sdists-v9/.git`: Read-only file system (os error 30)
```

Subsequent commands used `UV_CACHE_DIR=/tmp/devteam-uv-cache`. An early focused run, `uv run python -m unittest tests.test_runner.HarnessSteps`, failed because my new fixtures omitted the mandatory epic parent. All four tests failed in setUp with the same error; output excerpts:

```text
EEEE
ERROR: test_failure_waits_for_retry_or_restart (tests.test_runner.HarnessSteps.test_failure_waits_for_retry_or_restart)
ERROR: test_harness_steps_run_without_engine_checkout_or_run_count (tests.test_runner.HarnessSteps.test_harness_steps_run_without_engine_checkout_or_run_count)
ERROR: test_pr_decision_holds_checkout_until_terminal (tests.test_runner.HarnessSteps.test_pr_decision_holds_checkout_until_terminal)
ERROR: test_registry_matches_the_validated_actions (tests.test_runner.HarnessSteps.test_registry_matches_the_validated_actions)
devteam.backlog.InvalidRecord: story requires a parent
Ran 4 tests in 0.008s
FAILED (errors=4)
```

Corrected the fixtures by creating an epic and passing its ID. The TUI fixture also reloads its workflow after defining its harness steps. The ordinary workflow/runner command then passed without any runtime helper:

```text
........................
----------------------------------------------------------------------
Ran 24 tests in 0.323s

OK
```

Ordinary TUI runs stalled after test completion in Python's async executor shutdown; the original combined unit run and project check were interrupted (exit 130), and an unchanged TUI test reproduced the stall under a 15-second timeout (exit 124, output `.`). A minimal `asyncio.run(asyncio.to_thread(lambda: None))` also stalled under both available Python versions. Diagnostic stacks showed `BaseEventLoop.shutdown_default_executor` waiting despite its future being finished. No repository code or tests were changed to bypass this environment problem.

For the final TUI and project-check runs only, `PYTHONPATH=/tmp/story-010-python-wakeup` loaded a temporary `sitecustomize.py` that schedules a 50ms event-loop wakeup while calling Python's original executor shutdown, cancelling that timer afterwards. This is an environment qualification: these runs pass with that helper, not an unqualified pass under the sandbox's ordinary shutdown. The helper is outside the repository and changes no application/test logic.

`UV_CACHE_DIR=/tmp/devteam-uv-cache PYTHONPATH=/tmp/story-010-python-wakeup uv run python -m unittest tests.test_workflow tests.test_runner tests.test_tui` exited 0; actual output:

```text
...................................Executing <Task pending name='screen_update' coro=<Timer._run_timer() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/timer.py:146> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.127 seconds
......
----------------------------------------------------------------------
Ran 41 tests in 24.487s

OK
```

`UV_CACHE_DIR=/tmp/devteam-uv-cache PYTHONPATH=/tmp/story-010-python-wakeup uv run python -m devteam check` exited 0; actual output:

```text
uv run python -m unittest discover -s tests
................................................................................Executing <Task pending name='message pump Note()' coro=<MessagePump._process_messages() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/message_pump.py:571> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.118 seconds
....................
----------------------------------------------------------------------
Ran 100 tests in 42.986s

OK

check passed; full output: /home/tarttelin/projects/pyruby/dev-team/backlog/log/check/20261007T115704562110.log
```

`UV_CACHE_DIR=/tmp/devteam-uv-cache uv run python -m devteam backlog validate` exited 0; actual output:

```text
EPIC-001   -            -                  Workflow-driven work items
EPIC-002   -            -                  Portable launch
EPIC-003   -            -                  GitHub and CI delivery
EPIC-004   -            -                  Staging, user testing and release
EPIC-005   -            -                  Sprint zero and product specialists
REQUEST-001 done         -                  As a customer using dev-team tui, I want to be able to see what an agent is curr
REQUEST-002 done         -                  When the publisher publishes a work-item creating a PR in github, it currently m
STORY-001  done         -                  Define the workflow in JSON and track each item's step
STORY-002  done         -                  Run agent-owned steps
STORY-003  done         -                  See work items and their steps in a terminal UI
STORY-004  done         -                  Act on human-owned steps in the terminal UI
STORY-005  done         -                  Analyse a request with the team and create work items from it
STORY-006  ready        human              Launch the team from any product directory
STORY-007  done         -                  Work in the checkout on a branch per item, with the backlog on its own branch
STORY-008  done         -                  Stream agent output live to log and listener
STORY-009  captured     human              Live agent output pane in the TUI
STORY-010  implement    agent:implementer  Hold a published item for the customer's PR decision
STORY-011  ready        human              Bring local main in line with origin when a PR is merged
STORY-012  analysis     agent:analyst      Return a rejected PR's comments to implement
STORY-013  captured     human              Re-publish updates the existing PR
```

`git diff --check` exited 0 with no output. `rg -n 'gh pr (merge|close)' devteam prompts/publish.md roles/publisher.md` and the same search over `git diff -- devteam prompts/publish.md roles/publisher.md` each exited 1 with no output (no matches). Publisher prompt and role files are unchanged.

All changes are left in the working tree; no commit was made in either project worktree. Checkout-switching tests create commits only in their disposable temporary repositories.

## Tests

New suite `tests/test_pr_decision.py`, driven through `python -m devteam backlog ...` and `python -m devteam run --once` against a throwaway product with a stub `claude` on PATH (the stub writes its argv file only if started, so a missing file shows no agent ran). Run one test with `uv run python -m devteam check tests.test_pr_decision.<Class>.<test>`; the module with `uv run python -m devteam check tests.test_pr_decision`.

- 1 `DefaultWorkflowShape.test_done_is_reachable_from_publish_only_through_the_pull_request`; `PullRequestDecision.test_published_item_waits_for_the_customer_instead_of_reaching_done`
- 2 `DefaultWorkflowShape.test_pull_request_is_the_customers_and_leads_to_the_harness_steps`; `PullRequestDecision.test_customer_can_only_move_a_pull_request_to_merged_or_rejected`
- 3 `DefaultWorkflowShape.test_accept_keeps_its_three_transitions`; `PullRequestDecision.test_accept_still_finishes_directly_and_the_pr_path_still_leads_to_publish`
- 4 `DefaultWorkflowShape.test_harness_steps_complete_to_done_and_implement`; `test_merged_decision_is_completed_by_the_harness_without_an_agent`; `test_rejected_decision_returns_the_item_to_implement_without_an_agent_at_rejected`
- 5 `PullRequestDecision.test_default_workflow_validates_through_the_backlog_command`; `test_repository_backlog_validates_with_the_new_workflow` (plus `tests.test_workflow`)
- 6 Workflow validation is not reachable from the command line (workflows load from the repository's fixed `workflows/` directory), so this stays with the implementer's `tests.test_workflow.WorkflowDefinition.test_invalid_harness_actions_and_outcomes_name_the_step`.
- 7, 13 The two harness decision tests above (no stub started, move reported, `completed -> <target>`); engine-less dispatch and no run count also in `tests.test_runner.HarnessSteps`.
- 8 Failure handling needs an injected failing action, so it stays with `tests.test_runner.HarnessSteps.test_failure_waits_for_retry_or_restart`.
- 9 Not a runtime behaviour; checked by `rg -n 'gh pr (merge|close)' devteam prompts/publish.md roles/publisher.md` (no matches).
- 10 TUI behaviour stays with `tests.test_tui.Acting.test_pr_decision_notes_and_harness_labels`; the CLI `-m` note on `rejected` is covered by the rejected test above.
- 11 `PullRequestHoldsTheCheckout.test_item_awaiting_the_customers_pull_request_decision_blocks_other_code_changes` (real git product; `run --once` reports the wait and the branch is unchanged); `pull-request` as the human step is asserted in the same test.
- 12 README table is documentation, not tested automatically.
- 14 `uv run python -m devteam check` passes (113 tests).

## Review

Verdict: approve. No blocking findings.

Minor observations (none affect a criterion):

1. `devteam/runner.py` and `devteam/workflow.py` both define `HARNESS_ACTIONS` (a dict and a set). The registry-agreement test keeps them in step, so this is only a naming overlap.
2. The README intro sentence was extended onto one long line; cosmetic.
3. The harness note dialog wording ("Anything to record for the next steps?") is generic, which the challenge accepted as cosmetic.

Criteria satisfied:

1. `workflows/default.json`: `publish` has only `published` -> `pull-request`; `done` is reachable from `publish` only via `pull-request` -> `merged` -> `done`. Tests: `DefaultWorkflowShape` and `PullRequestDecision` in `tests/test_pr_decision.py`.
2. `pull-request` is `human` with exactly `merged` and `rejected` (json; test_pr_decision).
3. `accept` transitions are unchanged in the diff; pinned by `test_accept_keeps_its_three_transitions`.
4. `merged` is `harness:merged` -> `done`; `rejected` is `harness:rejected` -> `implement`; each has only `completed` (json; tests).
5. The default workflow loads and validates (`test_default_workflow_validates_through_the_backlog_command`, plus `tests.test_workflow`).
6. `workflow.build` rejects an unknown action and non-`completed` transitions, each naming the step; covered by `test_invalid_harness_actions_and_outcomes_name_the_step`.
7. `pending()` includes `step.harness`; `run_item` dispatches through `HARNESS_ACTIONS` and transitions on the returned name, with no engine call. The tests use a stub `claude` that would write a marker if started, and `HarnessSteps` covers the runner path.
8. The action runs inside the existing try block, so `StepFailed` takes the existing failure path; `test_failure_waits_for_retry_or_restart`.
9. `gh pr merge` and `gh pr close` appear nowhere in the diff or the code.
10. `owner_label` returns "harness"; `chosen()` skips the note for a move into the `merged` action and keeps it for `rejected`, saved as feedback; `test_pr_decision_notes_and_harness_labels`.
11. `pull-request` is a human step, so it shows as `needs_you`. `take_checkout` is untouched, and `PullRequestHoldsTheCheckout` shows another item waiting; it is released only at a terminal step.
12. The README table lists the three new steps and the `publish` row points to `pull-request`.
13. The placeholder actions only return `completed`; no checkout or run counting is added on the harness path.
14. The harness's own run: the project check passed, 113 tests OK.

## Test run

Run by the harness, 2026-10-07 12:02 UTC. Full output: `/home/tarttelin/projects/pyruby/dev-team/backlog/log/STORY-010/verify-20261007T120143362152.log`

Passed: `the project check`

```text
uv run python -m unittest discover -s tests
.................................................................................................................
----------------------------------------------------------------------
Ran 113 tests in 60.274s

OK
```
