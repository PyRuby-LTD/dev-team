# 07: Default workflow group 2 - implement and test on the item branch, with the checkout queue

**What to build:** Choosing `play` at `ready` (with optional feedback) starts the implementer on the item's own item branch in the checkout. A step holds the checkout when it is a git or check step, or an agent step whose role works on a branch per the roles configuration. Only one item's work holds the checkout at a time; others queue, and the TUI shows an item waiting for the checkout. One agent runs at a time. The implementer's output (branch, blocked by, libraries added, tech tasks, surprises, opinions) is recorded; a blocked implementer returns the item to `ready`. The tester writes or extends journey tests; a defect sends the item back to implement. Implementer and tester prompts are drafted for the author's review. This is milestone 2.

**Blocked by:** 06

**Status:** ready-for-agent

- [x] A journey test plays two items: the first works on its own item branch, the second waits for the checkout and then works on its own branch, and neither branch carries the other's changes
- [x] A tester `defect` returns the item to implement with the defects as pending input
- [x] The backlog stays on its own branch, separate from product code
- [x] Implementer and tester prompts are drafted and previewable, flagged for the author's review

## Comments

The harness takes the checkout before any step that uses it: an item holds the checkout while its branch is checked out and its current step works there, so the holder keeps it from implement through test and lets go at a customer step such as `ready`. A second item waits, with the reason shown beside it in the TUI, then switches the checkout back to the holder's base and makes its own `devteam/<id>` branch from there. The harness commits an agent's work on its branch once the agent submits.

`prompts/implement.md` and `prompts/test.md` are redrafted for YAML items from the implementer and tester briefs and `Development patterns.md`. They need the author's review; preview them with `uv run python -m devteam prompt implement` and `... prompt test`. Points to settle while reviewing:

- The prompts pass everything sent back (play feedback, defects, review findings, accept feedback) as YAML under one heading per entry, and leave how to treat each to the briefs.
- `verify_log` is the newest log of any check step in the item's workflow, so after `verify-publish` the implementer sees that run rather than `verify`'s.
- `test_pr_feedback.PullRequestFeedback.test_empty_feedback_and_prompt` asserts the original Markdown wording that `prompts/implement.md` no longer carries; it goes with the original harness in issue 13.
