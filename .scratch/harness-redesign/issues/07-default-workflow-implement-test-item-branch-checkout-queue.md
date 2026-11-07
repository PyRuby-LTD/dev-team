# 07: Default workflow group 2 - implement and test on the item branch, with the checkout queue

**What to build:** Choosing `play` at `ready` (with optional feedback) starts the implementer on the item's own item branch in the checkout. A step holds the checkout when it is a git or check step, or an agent step whose role works on a branch per the roles configuration. Only one item's work holds the checkout at a time; others queue, and the TUI shows an item waiting for the checkout. One agent runs at a time. The implementer's output (branch, blocked by, libraries added, tech tasks, surprises, opinions) is recorded; a blocked implementer returns the item to `ready`. The tester writes or extends journey tests; a defect sends the item back to implement. Implementer and tester prompts are drafted for the author's review. This is milestone 2.

**Blocked by:** 06

**Status:** ready-for-agent

- [ ] A journey test plays two items: the first works on its own item branch, the second waits for the checkout and then works on its own branch, and neither branch carries the other's changes
- [ ] A tester `defect` returns the item to implement with the defects as pending input
- [ ] The backlog stays on its own branch, separate from product code
- [ ] Implementer and tester prompts are drafted and previewable, flagged for the author's review
