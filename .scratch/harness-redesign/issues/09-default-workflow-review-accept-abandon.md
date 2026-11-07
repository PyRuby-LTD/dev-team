# 09: Default workflow group 4 - review, accept and abandon

**What to build:** The reviewer records findings, each as fix or task; an unmet or unproven criterion sends the item back to implement with the findings pending. At `accept`, the customer chooses `pr`, `revise` with feedback for the implementer, or `abandon`. Abandoning returns the checkout to the base branch, keeps the item branch for recovery, and finishes the item at `abandoned`. The review prompt is drafted for the author's review.

**Blocked by:** 08

**Status:** ready-for-agent

- [ ] A journey test covers review `revise` with findings reaching implement, then `approve` reaching `accept`
- [ ] Accept `revise` puts the customer's feedback in the implementer's pending input
- [ ] Abandon leaves the checkout on the base branch with the item branch still present
- [ ] The review prompt is drafted and previewable, flagged for the author's review
