# 08: Default workflow group 3 - sync, verify and resolve

**What to build:** After test, the item branch merges its base (`git:Sync`); conflicts go to the implementer at resolve, and a resolve it cannot do returns the item to `ready` with the merge aborted. The project's check runs on the branch (`harness:Check`); passing moves the item to review and failing sends it back to test. These harness steps perform their actions and return outcomes; only the loop records them. The resolve prompt is drafted for the author's review.

**Blocked by:** 07

**Status:** ready-for-agent

- [x] A journey test covers a clean sync and passing check reaching review
- [x] A journey test covers a conflicting sync resolved by a stub implementer, and a blocked resolve returning to `ready` with the merge aborted
- [x] A failing check sends the item back to test with the check's summary recorded
- [x] The original runner's sync and check code is deleted once the steps own it

## Comments

`git:Sync` and `harness:Check` now do their own work and return their output: a conflicted sync names the files under `conflicts`, which reach `resolve` as pending input, and a check records `summary` (its exit code or launch failure, then the end of its output). The default workflow declares these outputs on the sync and verify steps, including the publish variants.

When an agent on the item branch submits while a merge is in progress, the harness completes the merge if the outcome's next step keeps the checkout, and otherwise aborts it and discards what the agent left. So `resolved` (to `verify`) commits the merge and `blocked` (to `ready`) aborts it, without the harness knowing either step by name.

`prompts/resolve.md` is redrafted for YAML items and needs the author's review; preview it with `uv run python -m devteam prompt resolve`. Points to settle while reviewing:

- `resolve` gains a `blocked_by` output, as `implement` has, so the customer at `ready` can see why it stopped. The issue did not ask for this.
- The prompt tells the agent not to stage or commit; the harness stages everything when it completes the merge.
- `prompts/resolve-publish.md` is untouched and still uses `conflicted_files`, which the new harness does not supply; it belongs with the publish group in issue 10.

The original runner's sync, verify and resolve-merge code is deleted, with the original tests that drove items through them (`test_sync.Sync`, `test_check.VerifyStep`, four checkout-queue tests, the check cases in the dispatch tests and the runner registry check). `git.sync_branch` no longer records conflicts in git config, since nothing reads them now.
