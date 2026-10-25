---
id: STORY-025
type: story
title: Bring a story's branch up to date with its base before verify and publish
parent: EPIC-008
workflow: default
step: publish
---
As a customer, I want each story's branch brought up to date with the base branch, with conflicts resolved, before it is verified and again before it is published, so that independently built stories can be accepted and merged in any order without conflicting pull requests.

## Context

Each code-changing item branches from the base branch recorded in `branch.<branch>.base`. Once several independent stories run in turn, the base branch moves on (another story merges) while a story is in flight or waiting for review, and its pull request can conflict.

Agents often cannot write `.git` from their sandbox (see the comment in `Runner.invoke`, `devteam/runner.py`), so the runner commits for them. Bringing a branch up to date writes `.git` and must therefore be done by the harness.

Decisions:

- A new harness action fetches `origin` and rebases the item's branch onto `origin/<base>`. When that applies cleanly, the step completes.
- On a conflict the harness aborts the rebase, merges `origin/<base>` without committing, and hands the conflicted files to the implementer to resolve the conflict markers in a single round. The harness commits the merge afterwards. This avoids one round of resolution per commit.
- The workflow becomes `test -> sync -> verify -> review -> accept` and `accept --pr-> sync -> verify -> publish`, so the reviewer is never given a test run of code that has since changed, and the base may have moved while the item waited at `accept`. Step names are for analysis to choose, since step names are unique within a workflow.
- A verification failure after the pre-publish sync returns the item to `implement`, not `test`.
- Pushing a rebased branch needs `git push --force-with-lease`; today the runner pushes with `push -u` before the publisher, which would be refused.
- A dirty checkout or a missing base is a step failure, as for the `merged` harness action.

Needed before the story that releases the checkout at human-owned steps, which would otherwise produce conflicting pull requests.

## Analysis

What exists today, checked against the repository:

- `workflows/default.json` runs `test -> verify -> review -> accept`, and `accept --pr-> publish -> pull-request`. No step brings the branch up to date. Nothing fetches or rebases except the `merged` action, which fast-forwards the local base (`devteam/runner.py:54`, `devteam/git.py:52`).
- The `merged` action is the model for the new one: it raises `StepFailed` for a missing base (`branch.<branch>.base`) and for a dirty checkout, and it holds the checkout (`Runner.uses_checkout`, `runner.py:216`).
- Harness actions are a fixed set in two places (`workflow.py:11`, `runner.py:154`). `workflow.build` requires every harness step to have exactly one transition, `completed` (`workflow.py:88`).
- The `verify` check's `failed` transition goes to `test`. The story wants a different target (`implement`) after the pre-publish sync, so the two verifications cannot be the same workflow step. A step has one transition map, and step names are unique.
- The publisher role has `push = true`. `Runner.invoke` runs `git push -q -u origin <branch>` before the publisher starts (`runner.py:317`). That is refused once the branch has been rebased onto a moved base and the remote copy has the old history. Re-publication after a rejection goes through the same push.
- `Runner.invoke` commits agent work with `git.commit_all`, which runs `git commit -- <paths>`, with `.` when no paths are given (`git.py:71`). Git refuses a path-limited commit while a merge is in progress ("cannot do a partial commit during a merge"). I have not run this here, but it is documented git behaviour, so the existing post-agent commit would fail at a resolve step.
- `take_checkout` returns early when the checkout is already on the item's branch, so an agent step can start with a merge in progress. A dirty-checkout check, as in `merged`, would wrongly fail a resolve step whose conflicts are the whole point; it applies only to the start of a sync.
- The TUI skips the note prompt for `merged` by name (`tui.py:552`); other targets owned by `YOU`, `finished` or `checks` also skip it. A harness step such as `sync` falls into none of those cases, so it would prompt for a note that no agent reads. This is decided below.
- `README.md` (Workflow table, Branches section) and `docs/backlog.md` describe the workflow and will need to match.

The premise holds: the conflict risk is real and nothing today prevents it.

Decisions taken in this round (answering the challenge):

- Step names are fixed now: `test -> sync -> verify -> review -> accept`, and `accept --pr-> sync-publish -> verify-publish -> publish`. Each sync has its own conflict-resolution implementer step: `resolve` (after `sync`, then on to `verify`) and `resolve-publish` (after `sync-publish`, then on to `verify-publish`). Prompts are looked up by step name (`runner.py:157`), so there are two templates, `prompts/resolve.md` and `prompts/resolve-publish.md`; their wording may be identical.
- `sync` has two outcomes: `completed` (the branch is up to date and committed, with no agent needed) and `conflicted` (a merge with conflicts is waiting in the checkout). `workflow.build` must allow exactly these two for this action, and exactly `completed` for the other harness actions. This is the smallest change that keeps conflict handling in the workflow; I am stating it as an assumption, not asking.
- How the sync works: fetch `origin`. If `origin/<base>` is already an ancestor of the branch, nothing changes (`completed`). Otherwise, if the branch contains no merge commit from its base, try `git rebase origin/<base>`; clean means `completed`. If the rebase conflicts, abort it and fall through to the merge. If the branch already contains a merge commit from its base (left by an earlier conflict resolution), skip the rebase, because a plain rebase drops merge commits and replays the original conflict, and merge directly. The merge is `git merge --no-commit origin/<base>`. If it applies cleanly, the harness commits it and the outcome is `completed`, with no agent run. If it leaves conflicts, the outcome is `conflicted`.
- Resolve step exits: `resolved` moves to the matching verify step; `blocked` moves to `ready`. On `blocked` the harness runs `git merge --abort` before the item leaves the step, so no half-finished merge is left holding the checkout. A replay then goes `ready -> implement -> test -> sync`, which syncs again.
- Committing the merge: when a merge is in progress, the runner after the `resolved` reply must stage everything and run a plain `git commit --no-edit` (no paths), producing a two-parent merge commit, instead of the path-limited `commit_all`. Before committing it checks that no previously conflicted file still contains conflict markers. If one does, the step fails, nothing is committed, and the merge is left in place so the step can be retried (a retry starts with the merge already in progress, which `take_checkout` permits). The dirty-checkout rule applies only to the start of a sync, not to a resolve step.
- Forced push and "foreign" commits: the sync's own `git fetch` moves `origin/devteam/<id>`, and a rebase gives the team's own commits new identities, so neither a bare `--force-with-lease` nor ancestry against the current local branch can tell the customer's commits from the team's (after a rebase, the team's own A and B on the remote are not in the local A', B', C'). The harness therefore keeps a record, `branch.<branch>.pushed`, of the remote head it has accounted for: "every commit on the remote branch up to here is either ours or has been accepted". A remote commit is foreign when it is reachable from `origin/<branch>` and from neither the recorded head nor the local branch head as it stands before the step rewrites anything. Rebasing locally does not change the record, so the team's own earlier commits are never foreign; pulling a customer commit into the local branch makes it not foreign (this is the customer's recovery, and matches their answer to question 2: commits "not in the local branch").
- The record moves in exactly two places, both only when the remote branch exists: (1) after a `sync` or `sync-publish` passes the foreign check, and before it rewrites anything, the record is set to the current `origin/<branch>` tip; (2) after a successful push, it is set to the pushed head. Step (1) is what carries a pulled-in commit S through the rebase: S becomes S' locally, but the record already covers S, so `sync-publish` does not flag it. It also covers a branch pushed before this story (no record): the first sync that finds a remote branch and no record runs the check against the local head, and on passing sets the record to the remote tip before rewriting. If the remote branch does not exist, nothing is foreign and nothing is recorded (first push).
- Where it is enforced: both `sync` and `sync-publish` check before rewriting anything, and fail the step naming the foreign commits, leaving the record unchanged. The push before `publish` also fails, with the same message, when the remote branch has moved from the recorded head (a customer can add a commit between `sync-publish` and the push); the lease is pinned to the recorded head, so the fetch cannot defeat it. The remote is never overwritten when foreign commits exist. The customer confirmed (answer to question 2) that failing is wanted. Two recoveries, to be documented: pull the commits into the local branch (`git merge origin/<branch>` on the item's branch) and replay the step, so they are carried into the rebased branch; or reset the remote branch to the last published head to discard them, and replay the step.
- TUI: choosing `pr` at `accept` now targets a harness step, so no agent reads a note. The TUI skips the note prompt for sync steps, as it does for `merged` (`tui.py:552`), and moves the item straight in. The `rejected` action keeps its existing behaviour.

What would change:

1. A new harness action `sync` (`runner.py` `HARNESS_ACTIONS`, `workflow.py:11`) with the behaviour above, plus any git helpers it needs in `devteam/git.py`. It holds the checkout. It is a step failure when the base is unrecorded, the checkout is dirty, `origin/<base>` is missing after the fetch, or the remote PR branch has foreign commits.
2. `workflows/default.json`: new steps `sync`, `resolve`, `sync-publish`, `resolve-publish` and `verify-publish`; `test.written` goes to `sync`; `accept.pr` goes to `sync-publish`; `verify` still fails to `test`; `verify-publish` fails to `implement`.
3. `workflow.build` validation relaxed so that `sync` steps have the `completed` and `conflicted` transitions.
4. `Runner.invoke`: commit a finished merge as above, and abort the merge on `blocked` at a resolve step.
5. The pre-publish push is safe against foreign commits and works on a rebased branch, in place of plain `push -u`, and records the pushed head. A first push of a new branch still works.
6. Prompt templates `prompts/resolve.md` and `prompts/resolve-publish.md`.
7. TUI skip of the note prompt for sync steps.
8. `README.md` (Workflow table, Branches section) and `docs/backlog.md` updated.

## Acceptance criteria

1. The sync action brings the item's branch up to date with `origin/<base>`. With `origin/<base>` ahead of the merge-base and no conflicts, `origin/<base>` is an ancestor of the branch, the item's own changes are kept as commits, and the item moves to its verify step without any agent running.
2. If the branch is already up to date, the step completes and leaves the branch unchanged.
3. On a conflict, the rebase is aborted (no `.git/rebase-*` state remains) and `origin/<base>` is merged into the branch with no commit made. The conflicted files contain conflict markers and the item moves to the matching resolve step.
4. If the rebase conflicts but the merge fallback applies cleanly, the harness commits that merge and the item moves straight to verify with no agent run.
5. If the branch already contains a merge from its base (from an earlier conflict resolution) and the base has moved again, the sync merges rather than rebasing: the earlier merge commit is kept and the earlier conflict does not recur.
6. The resolve step's prompt names the conflicted files and the base, asks for the markers to be resolved in one round, and tells the implementer not to commit. After `resolved`, the harness commits the merge. The result is a merge commit whose parents are the branch's previous head and `origin/<base>`, and the working tree is clean. The item then goes to the matching verify step.
7. If any previously conflicted file still contains conflict markers when the implementer replies `resolved`, the step fails, nothing is committed, the merge stays in place, and the step can be retried.
8. If the implementer replies `blocked`, the merge is aborted, the branch is back at its previous head with a clean working tree, and the item is at `ready`.
9. The sync action fails the step (the item stays put, reported as for `merged`, retryable) when the checkout has uncommitted changes, no `branch.<branch>.base` is recorded, or `origin/<base>` cannot be fetched or does not exist. In each case no branch is switched or rewritten.
10. `workflows/default.json` runs `test -> sync -> verify -> review -> accept`, and `accept --pr-> sync-publish -> verify-publish -> publish`, with conflict-resolution steps `resolve` (after `sync`, then to `verify`) and `resolve-publish` (after `sync-publish`, then to `verify-publish`). The workflow loads without error and every step is reachable.
11. A `verify` failure returns the item to `test`. A `verify-publish` failure returns it to `implement`.
12. A sync step runs only when the checkout is available to the item and holds it while it runs, so other code-changing items wait, as at `merged`.
13. Publishing a branch that was rebased since its last push succeeds: the remote branch ends at the rebased head. A first push of a new branch still succeeds.
14. A foreign commit is one reachable from `origin/<branch>` and reachable from neither the recorded `branch.<branch>.pushed` head nor the local branch head as it stands before the step rewrites anything (decisions on the `pushed` record above govern; the record moves at each passing sync and each successful push, so it is not simply "the last pushed head"). A commit the customer has pulled into the local branch is therefore not foreign, and with no remote branch nothing is foreign. If the remote PR branch has gained a foreign commit (for example a commit suggestion applied on GitHub), it is never overwritten. The failure is reported by whichever comes first of `sync`, `sync-publish` and the push before `publish`, with a message naming the foreign commits; the remote branch is left as it was and the failing step does not rewrite the local branch. This includes a commit added after `sync-publish` has completed and before the push. Once the customer has dealt with the commits by hand, playing the step again can succeed.
15. Republish after rejection with a moved base succeeds: publish A and B, reject, the implementer adds C, the base branch gains a commit, nobody touches the remote. The syncs rebase to A', B', C', neither sync nor the push reports the team's own A and B as foreign, and the remote branch ends at the rebased head. The same flow succeeds for a branch pushed before this story, where no `pushed` record exists: the first sync records the remote tip before rewriting, so the later `sync-publish` and the push do not report A and B as foreign.
15a. Recovery by pulling: remote holds A, B and a customer commit S; the local branch ends at B; the sync fails naming S (criterion 14). The customer merges `origin/<branch>` into the local branch and replays the step. The sync passes, the rebase carries S's change into the rebased branch, `sync-publish` and the push do not report S as foreign, and the remote ends at a head that contains S's change.
15b. Recovery by discarding: after the failure in 15a, the customer resets the remote branch to B and replays the step. The sync passes and the remote ends at the rebased head without S.
16. Workflow validation accepts `sync` with `completed` and `conflicted`, and still rejects any other harness step with transitions other than its defined ones. An unknown action name is still rejected.
17. In the TUI, choosing `pr` at `accept` moves the item to `sync-publish` without asking for a note.
18. `README.md` (Workflow table and Branches section) and `docs/backlog.md` describe the new steps, the conflict handling and the forced push, including the two recoveries for commits found on the remote branch (pull them into the local branch, or reset the remote to the last published head to discard them).
19. The existing end-to-end flows (publish, republish after rejection, merged, rejected) still pass with the new workflow. The base-moved republish in criterion 15 is a separate flow from them.

Out of scope: releasing the checkout at human-owned steps; changing the `merged` action; resolving conflicts in the backlog branch.

## Questions

1. When someone adds commits to the pull request branch on GitHub (for example by applying a suggestion) and the item is then synced and published, what should happen to those commits? The assumed default is that the step fails with a message and leaves the remote branch alone, so you can deal with it. The alternative is to bring those commits into the local branch automatically before syncing. Which do you want?

   **Answer:** I don't understand the question, sketch out a flow with an example.

2. Here is the same question as a worked example. Story STORY-030 has been published as pull request #40 from branch `devteam/STORY-030`. The branch holds commits A and B, both made by the dev team. You review the pull request on GitHub and click "Commit suggestion" on one comment. GitHub adds commit S to `devteam/STORY-030` on the remote. Your machine's copy of the branch still ends at B, so it does not have S. You then reject the item, the implementer makes commit C, and meanwhile `main` has moved on. Before publishing again the harness syncs: it rebases the local branch onto the new `main`, which rewrites A, B and C as new commits A', B' and C', and then pushes them over the remote branch. That push replaces what is on GitHub, so S would be lost without any warning. There are two ways to handle it. Option (a): the harness notices S on the remote that it does not have locally, stops with a message such as "the remote branch has commits that are not in the local branch: S", and leaves the remote untouched; you then deal with S yourself (for example by pulling it in or deciding to discard it) and play the step again. Option (b): the harness first pulls S into the local branch automatically, then rebases and pushes, so S survives but may itself need conflict resolution. The assumed default is (a), because it never discards your work and needs no extra logic. Is (a) acceptable, or do you want (b)?

   **Answer:** (a). If the remote PR branch has commits that are not in the local branch, fail the step with a message naming them and leave the remote untouched. I'll deal with them by hand.

## Challenge

Sound. The last round's only finding is fixed. Criterion 14 now uses decision 51's definition of a foreign commit, and it says the `pushed` record moves at each passing sync and each successful push. Criteria 14, 15, 15a and 15b now agree. I traced each of those flows against the rule, and each ends where its criterion says.

I checked the code facts again on this branch, and they hold:

- `workflows/default.json` has no step that brings a branch up to date.
- Harness actions are a fixed set in `devteam/workflow.py:11` and `devteam/runner.py:195`. `workflow.build` allows only `completed` (`devteam/workflow.py:88`).
- `uses_checkout` names `merged` and `abandon` explicitly (`devteam/runner.py:260`), so criterion 12 is a real change.
- `take_checkout` returns early when the checkout is already on the item's branch (`devteam/runner.py:305`). A resolve step can therefore start with a merge in progress.
- The publisher runs `push -q -u` before it starts (`devteam/runner.py:362`).
- The post-agent commit is path-limited (`devteam/runner.py:382`, `devteam/git.py:76`).
- The TUI skips the note prompt by action name (`devteam/tui.py:552`).

There are two further path-limited commits in the agent path. One commits the item copy before the agent runs (`devteam/runner.py:360`), and it would fail during a merge in the same way. It does not apply here: only the publisher has `record = true` (`config/roles.toml:89`), and the publisher never runs while a merge is in progress. The backlog is a separate worktree on `devteam-backlog`, excluded from the code checkout, so a rebase does not touch it.

The riskiest assumption is decision 37: git refuses a path-limited commit while a merge is in progress. That claim is unverified, but the item does not depend on it. Decision 50 replaces the commit at a resolve step whatever git does, and criteria 6 and 7 judge the result.

A competent engineer can implement the item as written, and a reviewer can tell from criteria 1 to 19 whether they have.

## Implementation

Implemented the sync harness action, both workflow paths and resolve prompts. Sync checks the recorded base, clean checkout and remote commits before switching or rewriting; it rebases clean branches and falls back to one merge for conflicts, preserving earlier base merges. The harness remembers the originally conflicted paths across retries, refuses remaining markers, commits resolved merges without a path restriction, and aborts and clears resolution work on `blocked`.

Publication now checks remote history and uses an explicit force-with-lease expectation. The `branch.<branch>.pushed` record advances at passing syncs and successful pushes, including adoption of legacy published branches and customer commits incorporated locally. The TUI skips notes for sync actions. README and backlog documentation describe the workflow, conflict handling, publication and both customer recoveries. Existing journey setup now follows the additional sync and verification steps.

Checks and evidence (all paths relative to the repository):

- Direct unit tests: `python -m unittest tests.test_sync tests.test_workflow tests.test_checkout`: 32 passed, `backlog/log/STORY-025/unit-confirmation.log`.
- After the final blocked-resolution cleanup change: `python -m unittest tests.test_sync tests.test_runner`: 27 passed, `backlog/log/STORY-025/resolution-final.log`.
- `python -m unittest tests.test_tui`: 38 passed, `backlog/log/STORY-025/tui-final.log`.
- `python -m unittest tests.test_pr_decision`: 13 passed, `backlog/log/STORY-025/pr-decision-final.log`.
- Existing journeys: `python -m unittest tests.test_republish tests.test_merged_cli tests.test_merged_detection_cli`: 16 passed, `backlog/log/STORY-025/journeys-final.log`.
- Earlier affected-module runs also covered `tests.test_merged` successfully. Initial failures were superseded workflow expectations and the changed fetch-before-push failure message; corrected and rerun. Captured failures remain in `backlog/log/STORY-025/unit.log`, `backlog/log/STORY-025/targeted.log` and `backlog/log/STORY-025/unit-final.log`.
- `uv build` initially failed because its default cache is read-only (`backlog/log/STORY-025/build.log`). Retried successfully with `UV_CACHE_DIR=/tmp/devteam-uv-cache`; final source distribution and wheel build passed (`backlog/log/STORY-025/build-final.log`).
- `git diff --check`: passed, `backlog/log/STORY-025/diff-check.log`. No separate lint or type-check commands are configured. The full suite was not run, as requested; no workflow check had run when this work started.

Acceptance criterion coverage:

| Criterion | Coverage and reason |
| --- | --- |
| 1 | Unit: `Sync.test_clean_rebase_and_noop`, real repositories and runner transition; no engine runs. |
| 2 | Unit: the same test checks unchanged HEAD on a repeated sync. |
| 3 | Unit: conflict fixture exercised by resolution tests checks markers, unchanged HEAD, resolve transition and absence of rebase state. |
| 4 | Unit: `test_rebase_conflicts_but_final_tree_merges_cleanly` checks both merge parents and a clean checkout without an agent. |
| 5 | Unit: `test_conflict_resolution_and_later_merge_preserve_parents` keeps the previous merge as first parent on the next sync. |
| 6 | Unit: resolution test checks real two-parent merge and clean tree, and the pre-publish variant checks its matching verify target. Prompt wording has no automated test; prose is left to human judgement. |
| 7 | Unit: `test_markers_fail_and_retry_even_when_staged` proves failed resolution leaves HEAD and merge intact, including after staging, then succeeds on retry. |
| 8 | Unit: `test_blocked_aborts` checks prior HEAD, clean checkout, no merge state and ready transition, including an extra resolution file. |
| 9 | Unit: `test_preconditions_preserve_checkout` checks dirty, unrecorded/missing base and fetch failure without switching or changing HEAD. |
| 10 | Existing workflow definition tests cover loading and changed entry transitions. The remaining transition map is declarative plumbing inspected directly; no new test restates it. Both conflict paths are exercised by unit tests. |
| 11 | Unit: `test_publish_conflict_and_verification_failure_route` invokes both failed checks and proves their different destinations. |
| 12 | Unit: `test_sync_claims_checkout_and_waits_for_other_users` proves sync participates in the existing checkout claim mechanism. Existing checkout tests cover branch ownership. |
| 13 | Unit: `test_republish_with_and_without_record` checks first push and rebased push against a real bare remote. |
| 14 | Unit: `test_foreign_commits_fail_sync_and_push_then_pull_recovery` checks named foreign commits, unchanged local/remote heads and unchanged record on sync/push failure. A foreign commit introduced after a recorded publication exercises the pre-push guard independently of sync. |
| 15 | Unit: `test_republish_with_and_without_record` builds A/B, pushes, adds C, moves base, syncs twice and pushes, with and without the legacy record. Existing rejection journey remains covered separately. |
| 15a | Unit: `test_foreign_commits_fail_sync_and_push_then_pull_recovery` incorporates the customer commit, moves base, syncs twice and pushes; the customer change survives. |
| 15b | Unit: `test_discard_recovery` resets the remote, retries sync and publishes without the discarded change. |
| 16 | Unit: `SyncWorkflow.test_harness_validation` and existing workflow validation tests cover exact sync outcomes, other harness restrictions and unknown actions. |
| 17 | Left to tester's journey tests: choosing `pr` through the running TUI is a user interaction. The implementation is a direct addition to its existing harness-action skip list; no unit test for that plumbing. |
| 18 | No automated test: documentation and wording are left to human judgement at review. |
| 19 | Existing publish, rejection/republish, merged and PR-decision journey tests pass after updating their setup paths. No new journey suite was authored. |

No criteria are blocked.

## Tests

Journey tests: no new journey was needed for the sync mechanics. The existing journeys cover the changed flow and were brought in step with the new workflow (criterion 19): `tests/test_republish.py`, `tests/test_pr_decision.py`, `tests/test_merged_cli.py`, `tests/test_merged_detection_cli.py`, `tests/test_pr_feedback.py`, `tests/test_requests.py` and `tests/test_run_evidence.py` now pass through `sync`, `sync-publish` and `verify-publish`. The story-to-publication journey in `tests/test_run_evidence.py` runs the real harness sync against a real repository and bare remote, and checks the reviewer and publisher see the right check logs.

Added: `test_choosing_pr_at_accept_moves_to_sync_publish_without_a_note` in `tests/test_tui.py` (criterion 17).

Left to unit tests (`tests/test_sync.py`, `tests/test_workflow.py`, `tests/test_checkout.py`): criteria 1 to 16 and 15a/15b, as the implementer recorded.

Left to human judgement: criterion 18 (README and `docs/backlog.md` wording) and the prose of the resolve prompts.

Run one test on its own, for example:
`dev-team check tests/test_tui.py` (or any other test file named above).

Whole suite: passed, 349 tests, log `backlog/log/check/20261025T210605769029.log`.

## Test run

Run by the harness, 2026-10-25 21:11:29 UTC: passed (exit 0); duration 157.244 seconds.

## Review

No blocking findings. The harness's full run passed: 349 tests, `backlog/log/STORY-025/verify-20261025T210852156753.log`.

Minor observations, none blocking:

- `git.push_branch` (`devteam/git.py`): if a record exists but the remote branch has since been deleted (for example after a PR branch is auto-deleted), the lease expects the recorded head against an absent ref and the push is refused. This is a safe failure and is retryable by hand. It is not covered by a criterion.
- `rebase --abort` in `sync_branch` is run after any failed rebase, not only a conflict, so a non-conflict rebase failure falls through to the merge. Acceptable.

Criteria satisfied, with proving test:

- 1, 2: `Sync.test_clean_rebase_and_noop` (`tests/test_sync.py`); `git.sync_branch` returns `completed` on ancestor or clean rebase.
- 3, 6, 7, 8: resolution tests in `tests/test_sync.py` (`test_markers_fail_and_retry_even_when_staged`, `test_blocked_aborts`); code in `Runner.invoke` and `git.finish_merge` (plain `commit --no-edit`, marker check before commit, `merge --abort` on `blocked`). Prompt wording (criterion 6) is prose with a recorded no-test reason; I accept it, and the prompts name the files, base, one round and no commit.
- 4: `test_rebase_conflicts_but_final_tree_merges_cleanly`.
- 5: `test_conflict_resolution_and_later_merge_preserve_parents`; `merged_base` skips the rebase.
- 9: `test_preconditions_preserve_checkout`; the checks run before fetch or switch.
- 10, 11: `workflows/default.json` read directly, plus `test_publish_conflict_and_verification_failure_route` and the workflow tests. The recorded reason for 10 (declarative plumbing) is accepted. Every step is reachable.
- 12: `uses_checkout` includes `sync`, with a `Waiting` check; `test_sync_claims_checkout_and_waits_for_other_users`.
- 13, 14, 15, 15a, 15b: `test_republish_with_and_without_record`, `test_foreign_commits_fail_sync_and_push_then_pull_recovery`, `test_discard_recovery`. They use real bare remotes, and `check_foreign` implements the decision-51 definition.
- 16: `SyncWorkflow.test_harness_validation`.
- 17: `test_choosing_pr_at_accept_moves_to_sync_publish_without_a_note` in `tests/test_tui.py`.
- 18: README and `docs/backlog.md` diffs describe the steps, conflict handling, the forced push and both recoveries. The recorded reason (documentation is left to human judgement) is accepted on reading the diff.
- 19: the existing journeys were updated and pass in the full run.
