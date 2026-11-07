# 09: Default workflow group 4 - review, accept and abandon

**What to build:** The reviewer records findings, each as fix or task; an unmet or unproven criterion sends the item back to implement with the findings pending. At `accept`, the customer chooses `pr`, `revise` with feedback for the implementer, or `abandon`. Abandoning returns the checkout to the base branch, keeps the item branch for recovery, and finishes the item at `abandoned`. The review prompt is drafted for the author's review.

**Blocked by:** 08

**Status:** ready-for-agent

- [x] A journey test covers review `revise` with findings reaching implement, then `approve` reaching `accept`
- [x] Accept `revise` puts the customer's feedback in the implementer's pending input
- [x] Abandon leaves the checkout on the base branch with the item branch still present
- [x] The review prompt is drafted and previewable, flagged for the author's review

## Comments

The workflow already routed review, accept and abandoning; this issue gives `git:Abandon` its own action. After the harness takes the checkout for the item, the step switches it to the branch's recorded base, leaving `devteam/<id>` where it was. It shares its preconditions (a recorded base, nothing uncommitted) with `git:Sync`.

`prompts/review.md` is redrafted for YAML items and needs the author's review; preview it with `uv run python -m devteam prompt review --item <id>`. Points to settle while reviewing:

- The prompt shows the reviewer what `implement` and `test` last recorded, including the implementer's surprises and opinions. `roles/reviewer.md` says not to seek the implementer's account as evidence, and still speaks of a per-criterion test record that `implement`'s output no longer has. The brief is the author's to change.
- `approve` is told to require that every finding is a `task`, so an outstanding `fix` always sends the item back. The workflow's `approve` meaning speaks only of criteria.
- Every piece of customer feedback on the item is shown, including `ready`'s `rework` feedback and earlier `accept` `revise` rounds already addressed.
- The glossary check applies to every item, as `Development patterns.md` asks, not only those with `glossary_changes`.

The original runner's abandon action is deleted, with `tests/test_abandon.py` and the dependency test that abandoned an item through the original runner. `depends_on` blocking on an abandoned item has no equivalent in the new harness yet. The assertion in `tests/test_checkout.py` on the original runner's rendering of the old review prompt is removed.
