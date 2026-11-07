# 08: Default workflow group 3 - sync, verify and resolve

**What to build:** After test, the item branch merges its base (`git:Sync`); conflicts go to the implementer at resolve, and a resolve it cannot do returns the item to `ready` with the merge aborted. The project's check runs on the branch (`harness:Check`); passing moves the item to review and failing sends it back to test. These harness steps perform their actions and return outcomes; only the loop records them. The resolve prompt is drafted for the author's review.

**Blocked by:** 07

**Status:** ready-for-agent

- [ ] A journey test covers a clean sync and passing check reaching review
- [ ] A journey test covers a conflicting sync resolved by a stub implementer, and a blocked resolve returning to `ready` with the merge aborted
- [ ] A failing check sends the item back to test with the check's summary recorded
- [ ] The original runner's sync and check code is deleted once the steps own it
