---
id: STORY-024
type: story
title: Hold a story back until the stories it depends on have merged
parent: EPIC-008
workflow: default
step: publish
---
As a customer, I want to say that a story depends on other stories, so that it is not started from the base branch before the work it builds on has merged, while stories that do not depend on each other can run one after another.

## Context

Work item front matter has no dependency field today; `FIELDS` in `devteam/backlog.py` is `id, type, title, parent, workflow, step`, and `docs/backlog.md` documents them. Each code-changing item branches from the base branch the checkout was on (`take_checkout` in `devteam/runner.py`), so a story started before its dependency merges cannot see that dependency's code.

Decisions:

- A new optional front-matter field, `depends_on`, holds a list of item IDs.
- Validation reports unknown IDs, self-references and dependency cycles per file, in the style of the existing parent checks.
- An item whose dependencies have not all reached `done` does not start its first branch-role step (while it has no `devteam/<id>` branch); it is reported as waiting, naming the unfinished dependencies, the same way checkout waits are reported. Steps that do not use the checkout, such as analysis, are not held back.
- The analyst and product owner may set `depends_on` when they capture or analyse work; how they are told to is part of this story.

- A dependency is satisfied only at `done`. STORY-027 removes the route to `done` without a pull request, so `done` means the dependency merged. A dependency at `abandoned` (also from STORY-027) never satisfies it: the dependent item is reported as blocked by the abandoned item until the customer edits its `depends_on`. STORY-027 must be done before this story is played.

Needed before the story that releases the checkout at human-owned steps, which would otherwise start dependent stories too early.

## Analysis

What exists today (checked in the repository):

- `FIELDS` in `devteam/backlog.py` is closed; `validate_metadata` rejects any other key, and `validate_links` holds the parent checks (missing, wrong type, cycle, quarantine of descendants). Dependency checks belong beside them.
- `Runner.claim` in `devteam/runner.py` decides whether a pending step may start. It already reports waits through `note_waiting` (shown by the terminal UI as the held reason) and sets `checkout_user` only when it lets a checkout step through. A dependency hold placed there, before `checkout_user` is taken, holds the story without blocking the checkout for other stories, which is what lets independent stories run one after another.
- Steps that use the checkout are those owned by `check`, the harness `merged` action, and roles with `branch = true` (implementer, tester, reviewer, publisher). Analysis, challenge and the other non-branch roles are not held.
- Agents cannot set front matter today. `Runner.invoke` fails the step with "the agent changed or broke the item's front matter" if the metadata differs after the run, and the work-item prompt says the same. `devteam backlog capture` has only `--id`, `--parent` and `--file`. So "the analyst and product owner may set `depends_on`" needs a harness-side way to do it; editing the file is not enough.
- `docs/backlog.md` documents the fields and the validation list; `prompts/analysis/product-owner.md` and the analyst prompt describe capture.
- STORY-027 (not yet landed) introduces the `abandoned` terminal step. This story is written against step names `done` and `abandoned`.

Assumptions (stated, not questions):

- `depends_on` is allowed on stories, tasks and bugs. Epics and requests must not carry it (epics carry no workflow; requests are analysis-only), reported like the other epic/request restrictions.
- The value is a list of item IDs; an empty list or an absent field means no dependencies. A non-list, a non-ID entry or a duplicate entry is invalid.
- A dependency may be a story, task or bug. One pointing at an epic is invalid since an epic never reaches `done`. One pointing at a request is invalid too: requests use the analysis workflow, where `done` means the analysis was approved, not that anything merged, and criterion 6 relies on `done` meaning merged.
- A dependency that itself has validation errors counts as unfinished and makes the dependent item report an error naming it, as a bad parent does today.
- "Satisfied" means the dependency's current step is named `done`; "abandoned" means a step named `abandoned`.
- The hold applies only to an item that has not yet branched: no local `devteam/<id>` branch exists. Once the branch exists (including on re-entry after `blocked` -> `ready` -> `play`), the item is never held, because the checkout stays on its branch and holding it would deadlock the runner against the item it waits for (`take_checkout` makes every other item wait while a non-terminal item holds the checkout). Adding or changing `depends_on` on an item that has already branched therefore has no effect on that item; this is documented, not an error. The abandoned-dependency block (criterion 7) follows the same rule. Check and harness steps are never held.
- The hold is re-evaluated on every scan, so it lifts without a restart when the last dependency reaches `done`, and edits to `depends_on` take effect on the next scan.
- Mechanism for agents: a `--depends-on` option on `devteam backlog capture` (repeatable or comma separated; implementer's choice, to be documented), and a new `devteam backlog` subcommand that sets or replaces the `depends_on` list of an existing item, rewriting only that front-matter line, validating the result and committing like `move`. The analyst and product owner prompts name these commands. The runner's "front matter changed" guard is relaxed in exactly one way: a step whose only front-matter change is a `depends_on` value that validates is accepted, whether written by the command or by hand; any other front-matter change still fails the step as today. The analyst can therefore set `depends_on` on the item it is analysing.

## Acceptance criteria

1. An item with `depends_on: [STORY-001, STORY-002]` in its front matter validates when both IDs exist; `docs/backlog.md` lists `depends_on` in the fields table and in the list of reported problems.
2. Validation reports, per file, and naming the offending ID or chain: an unknown ID; an item depending on itself; a dependency cycle (the message shows the cycle, as the parent cycle message does); an entry that is not an item ID; a repeated entry; `depends_on` that is not a list; `depends_on` on an epic or request; a dependency on an epic; a dependency on a request (the message says a request's `done` does not mean merged work). A dependency that itself fails validation makes the dependent item invalid with a message naming that dependency, as a bad parent does today, and the dependent item's child tasks are quarantined through the existing parent check. Unrelated items stay valid and validation writes nothing.
3. An item that has no `devteam/<id>` branch yet, and whose dependencies are not all at the step `done`, is not started at a branch-role step. `Runner` reports it as waiting with a message naming each unfinished dependency and its current step (for example "waiting for STORY-001 (implement), STORY-002 (ready) to be done"), through the same mechanism as checkout waits, so the terminal UI shows it as held.
4. An item that already has its `devteam/<id>` branch is not held by `depends_on`, whatever state its dependencies are in, so it can never stop the story it depends on from taking the checkout. While one story is held for its dependencies, another story with no unfinished dependencies can take the checkout and run; the held story does not occupy the checkout or block the other. When there are no dependencies at all, behaviour is unchanged.
5. Steps that do not use the checkout, such as analysis, challenge and answering, run for a story whose dependencies are unfinished.
6. When the last dependency reaches `done`, the held story starts on its next scan without restarting the runner, and branches from the base branch the checkout is returned to, so it can see the merged work.
7. A dependency at `abandoned` never satisfies the dependent item. An unbranched item is reported as blocked, naming the abandoned item and saying the customer must edit `depends_on`; it is not started. Editing `depends_on` to remove the abandoned item releases it.
8. The analyst and product owner can set the field without editing front matter by hand: `devteam backlog capture` accepts the dependencies of the new item, and a `devteam backlog` command sets the list on an existing item. Both reject invalid values with the validation message and leave the file untouched; the successful change is committed to the backlog branch like other backlog edits. A step whose only front-matter change is a valid `depends_on` value is not failed as a front-matter change; a step that changes any other front-matter key, or writes an invalid `depends_on`, still fails with the existing message.
9. The analysis and product owner prompts (`prompts/analysis.md`, `prompts/analysis/product-owner.md`) tell those roles when and how to record dependencies, and the README and `docs/backlog.md` describe `depends_on`, the hold and the abandoned case.
10. Existing items without `depends_on` keep rendering and moving exactly as before; `move` still rewrites only the `step` line.

Out of scope: releasing the checkout at human-owned steps (the later story this one enables); deleting or recovering the branches of abandoned items; migrating existing items.

Ordering: STORY-027 is a hard prerequisite and this story is not to be played until it is done. Without it, `accept` -> `done` skips the `merged` fast-forward, so a dependency could reach `done` with its work absent from the base branch and criterion 6 would not hold. The `abandoned` step is introduced by STORY-027.

## Challenge

Verdict: sound. A competent engineer could implement this item as written, and a reviewer could tell whether they had. This is the third round. The request-dependency finding from round two is resolved: criterion 2 and the assumptions now make a dependency on a request invalid, for the stated reason.

I checked the item's claims about the code against the repository again, and they hold:

- `FIELDS` is closed and `validate_metadata` rejects other keys (`devteam/backlog.py:52`, `:94-96`).
- The parent checks and the quarantine loop that the dependency checks are to sit beside are in `validate_links` (`devteam/backlog.py:157-190`).
- Requests always get the `analysis` workflow (`devteam/backlog.py:268`).
- `claim` takes `checkout_user` only for checkout steps, so a hold placed before that does not occupy the checkout (`devteam/runner.py:219-236`).
- `uses_checkout` covers check, the `merged` harness action and branch roles (`devteam/runner.py:215-217`).
- `take_checkout` keeps every other item waiting while a non-terminal item holds the checkout, which is why the hold is limited to unbranched items (`devteam/runner.py:265-268`).
- The front-matter guard is at `devteam/runner.py:333-335`.
- `capture` has only `--id`, `--parent` and `--file` (`devteam/cli.py:107-113`).
- Agents may already run `dev-team` commands unattended (`--allowedTools` in `config/roles.toml`), so the proposed `dev-team backlog` command is reachable by the analyst and product owner without a configuration change.

STORY-027 is still at `answering`. The item states plainly that it is a hard prerequisite and must not be played first, and the runner cannot enforce that until this story exists. The customer should keep it at `ready` until STORY-027 reaches `done`.

No checks were run for this challenge. Everything above comes from reading the code, the configuration, the workflows and the STORY-027 item.

## Response to challenge

1. Accepted. The hold is limited to items with no `devteam/<id>` branch; criteria 3, 4 and 7 and the assumptions state it, including re-entry after `blocked`. Gaining a dependency after branching has no effect (documented).
2. Accepted. STORY-027 is a hard prerequisite; the "if this story lands first" route is removed.
3. Accepted. The guard accepts a step whose only front-matter change is a validating `depends_on` and still fails any other change; both halves are in criterion 8.
4. Accepted. A dependency with validation errors is now in criterion 2.

Second round:

5. Accepted. A dependency on a request is invalid, alongside the epic case and for the same reason: `done` is only a merge signal for stories, tasks and bugs. This is in the assumptions and criterion 2. If the customer later wants stories to wait on an approved request, that is a separate decision.

## Implementation

Status: implemented. The earlier prerequisite blocker is resolved: merge commit `6d11f8c` (STORY-027, PR #19) is an ancestor of this branch. The default workflow includes `abandoned` and reaches `done` only through `merged`. Evidence: `backlog/log/STORY-024/prerequisite-landed.log`. No prerequisite code was imported or reimplemented here.

Changes (including the implementation already present on this branch):

- Added optional dependency metadata and per-file validation, including graph cycles, invalid targets and propagation through dependency and parent links.
- Added repeatable `--depends-on ID` capture options and `dev-team backlog depends-on <item-id> [ID ...]` to replace or clear dependencies. Edits validate before writing, preserve other fields and body text (including CRLF), and commit only the edited item on the backlog branch.
- Added dependency waits before branch roles claim the checkout. Existing local item branches, non-branch roles, checks and harness steps are exempt. Abandoned dependencies report a customer-action block; edits and completed dependencies are re-evaluated on the next scan.
- Relaxed the agent front-matter guard only for a valid dependency change. Updated the shared protocol, analyst and product-owner guidance, README and backlog documentation.
- Removed the obsolete default-workflow stub from `DependencyMerge`. Its abandoned-dependency test now uses the real `accept -> abandoning -> abandoned` transition and harness action before checking the hold and release. The real merged-base test now runs against the landed prerequisite without modifying the workflow.
- Replaced the old negative fixture that treated `depends_on` as unknown with a genuinely unknown field.

Acceptance coverage (tests are in `tests/test_dependencies.py` unless stated otherwise):

1. Unit tests: `DependencyValidation.test_valid_ids_roundtrip_for_stories_tasks_and_bugs` and `DependencyWrites.test_cli_capture_and_replace_commit_only_item_and_reject_without_writing` cover valid fields and multiple IDs. Documentation has no automated test; prose is left to human judgement at review.
2. Unit tests: all four `DependencyValidation` tests cover malformed values, duplicate entries, unknown/self links, epic/request restrictions, cycles with named chains, invalid dependencies and quarantine of child tasks. They also prove unrelated items stay valid and validation writes nothing.
3. Unit test: `DependencyScheduling.test_wait_lists_every_unfinished_dependency_without_claiming_checkout` checks the wait reason with IDs and steps, no branch and no checkout claim. Showing that held reason through the running terminal UI is left to the tester's journey tests; wording/presentation is left to human judgement.
4. Unit tests: `DependencyScheduling.test_existing_branch_bypasses_hold_even_with_abandoned_dependency` and `test_wait_lists_every_unfinished_dependency_without_claiming_checkout` prove branch exemption and independent work proceeding. Existing `tests.test_checkout` and `tests.test_runner` cover unchanged scheduling without dependencies.
5. Unit test: `DependencyScheduling.test_analysis_runs_with_unfinished_dependencies`. No separate tests for challenge or human answering: non-branch roles use the same branch-flag decision, and human-owned steps are not dispatched to an agent. No additional tester journey is required for that plumbing.
6. Unit tests: `DependencyScheduling.test_hold_lifts_only_after_last_dependency_is_done_on_same_runner` and `DependencyMerge.test_next_scan_starts_from_merged_base_without_restart` prove release after the last dependency, the real merged harness action, base selection and visibility of the merged commit. The landed default workflow now reaches `done` only through `merged`; the prerequisite workflow and abandonment unit tests are included in the focused run.
7. Unit tests: `DependencyMerge.test_abandoned_blocks_until_customer_removes_dependency` and the existing-branch exemption test cover abandoned blocking, customer instructions and release after editing, using the real default workflow and abandonment harness action. The existing-branch scheduling test retains its isolated custom-workflow fixture.
8. Unit tests: all three `DependencyWrites` tests cover CLI capture/edit, commits, rejected changes leaving files untouched, cycle rejection, repairing a bad link and preserving other text. Both `DependencyAgentEdits` tests prove command and handwritten valid edits pass and invalid dependencies or other metadata changes retain the existing failure message.
9. No automated test: prompt and documentation prose is left to human judgement at review.
10. Unit tests: existing `tests.test_backlog` roundtrip/move regressions, plus `DependencyWrites.test_value_rewrite_preserves_other_front_matter_and_body_and_move_only_changes_step`, prove metadata compatibility and that move still changes only the step line. No automated test for rendered presentation; left to human judgement at review.

Checks and evidence (this implementation pass):

- Latest supplied workflow-check status: no workflow check has run yet. No full suite was run during this pass.
- Direct focused run: `.venv/bin/python -m unittest tests.test_dependencies tests.test_backlog tests.test_backlog_writes tests.test_runner tests.test_checkout tests.test_requests tests.test_dispatch tests.test_merged tests.test_abandon.Abandon tests.test_workflow` — passed, 104 tests in 21.630 seconds. Includes the changed dependency test, all modified production modules' relevant tests, and the prerequisite merge/abandon workflow tests. Evidence: `backlog/log/STORY-024/unit-prerequisite-landed.log`.
- `UV_CACHE_DIR=/tmp/STORY-024-uv-cache uv build --out-dir /tmp/STORY-024-dist` — passed; source distribution and wheel built. Evidence: `backlog/log/STORY-024/build-prerequisite-landed.log`.
- `git diff --check` — passed. Evidence: `backlog/log/STORY-024/diff-check-prerequisite-landed.log`.
- `git -C backlog diff --check` — passed. Evidence: `backlog/log/STORY-024/backlog-diff-check-prerequisite-landed.log`.
- No lint or type-check command is configured in the project. The full regression suite remains for the later workflow step.

## Tests

Journey test: `tests/test_dependency_cli.py`, `DependentStoryFromTheCommandLine.test_story_is_held_until_its_dependency_is_cleared_and_then_starts`. Through the real `dev-team` command line, the customer captures a story with `--depends-on`, plays it, and `dev-team run --once` reports it waiting for the dependency without creating its branch or invoking an agent. The customer then clears the list with `dev-team backlog depends-on`, and the next run starts the story and creates its branch. This covers criteria 3, 6 (release on the next scan, by clearing the list; a dependency reaching `done` is left to unit tests), 8 (both commands) and part of 4.

Left to the implementer's unit tests (`tests/test_dependencies.py`): criteria 1, 2, 4 (checkout not occupied, branch exemption), 5, 6 (merged base), 7, 8 (rejections, guard) and 10.

Left to human judgement as prose or presentation: criterion 9 (prompts and documentation) and the wording of the held reason.

Run the journey on its own: `dev-team check tests.test_dependency_cli`. Whole suite passed (336 tests): `backlog/log/check/20261025T202107858982.log`.

## Test run

Run by the harness, 2026-10-25 20:26:03 UTC: passed (exit 0); duration 143.414 seconds.

## Review

Verdict: approve. No findings that block acceptance. The harness suite passed (336 tests): `backlog/log/STORY-024/verify-20261025T202339545997.log`.

Minor observations, not blocking:

- A self-dependency is reported twice (self-reference and a one-link cycle) in `devteam/backlog.py` `validate_links`. Harmless; both messages name the ID.
- The diff against `journey-tests-not-presentation` also shows STORY-027 files (abandon action, workflow, TUI tweak) because that base predates the merge of PR #19. They are the prerequisite, not scope creep in this story.

Criteria:

1. Met. `validate_metadata` accepts a list of IDs; `docs/backlog.md` lists the field and the reported problems. Proven by `DependencyValidation.test_valid_ids_roundtrip_for_stories_tasks_and_bugs`. Documentation wording is prose; accepted as left to human judgement and read in the diff.
2. Met. `validate_metadata` and `validate_links` cover non-list, non-ID, repeated, epic/request carrier, unknown, self, cycle (chain shown), epic and request targets, invalid-dependency propagation and quarantine of child tasks through the existing loop. Proven by the four `DependencyValidation` tests in `tests/test_dependencies.py`.
3. Met. `Runner.dependency_wait` returns "waiting for ID (step), ... to be done" and `claim` passes it to `note_waiting`. Proven by `DependencyScheduling.test_wait_lists_every_unfinished_dependency_without_claiming_checkout` and the journey `tests.test_dependency_cli` (held output, no branch, no agent prompt). Wording of the held reason is accepted as presentation.
4. Met. The wait is computed before `checkout_user` is taken, and returns None when `refs/heads/devteam/<id>` exists. Proven by `test_existing_branch_bypasses_hold_even_with_abandoned_dependency` and the no-checkout-claim test.
5. Met. `dependency_wait` returns None for non-branch roles. Proven by `test_analysis_runs_with_unfinished_dependencies`. The recorded reason for not testing challenge and answering separately (same branch-flag decision) is accepted.
6. Met. The hold is recomputed on every `claim` scan. Proven by `test_hold_lifts_only_after_last_dependency_is_done_on_same_runner` and `DependencyMerge.test_next_scan_starts_from_merged_base_without_restart`; the journey covers release by clearing the list.
7. Met. An abandoned dependency yields a "blocked by abandoned ... the customer must edit depends_on" reason, and edits release it. Proven by `DependencyMerge.test_abandoned_blocks_until_customer_removes_dependency`.
8. Met. `--depends-on` on capture and `backlog depends-on` (`Repository.set_dependencies`) validate before writing and commit. The guard in `Runner.invoke` ignores only `depends_on` and still fails when the result is invalid, since the item then drops out of `valid`. Proven by `DependencyWrites` (three tests), `DependencyAgentEdits` (two tests) and the journey.
9. Met by reading the diff: `prompts/analysis.md`, `prompts/analysis/product-owner.md`, README and `docs/backlog.md` describe when and how to record dependencies, the hold and the abandoned case. Prose, no automated test; accepted.
10. Met. The `depends_on` key is optional and `move` is untouched. Proven by the existing `tests.test_backlog` regressions and `DependencyWrites.test_value_rewrite_preserves_other_front_matter_and_body_and_move_only_changes_step`.
