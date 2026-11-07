# 16: Bug: a request's drafted stories are not grouped under an epic

**Type:** bug

**Status:** needs-triage

**Found in:** the milestone 1 demonstration by hand (ticket 03): capture, analyse, answer, draft.

**Current behaviour:** After a request was analysed, its questions answered and analysed again, the product owner drafted several stories. No epic was created, and none of the stories set `parent`, so the TUI lists them as loose items rather than grouped under an epic.

**Expected behaviour:** The stories drafted from a request are grouped under an epic: the product owner creates the epic first and each story names it as its `parent`, so the customer sees the body of work together (spec user story 21).

**Steps to reproduce:**
1. Start the TUI on a product and capture a request whose work divides into several stories.
2. Choose `analyse`, answer the product owner's questions, and choose `answered`.
3. Wait for the product owner to draft the work items.
4. Look at the drafted stories: there is no epic, and no story has a `parent`.

**Notes:** `prompts/analysis/product-owner.md` mentions "how the work divides into epics" and asks for epics to be created before their stories, but does not say when a request must have one, so creating an epic is left to the agent. Whether every request with more than one story needs an epic, and whether the harness should enforce it or only the prompt should ask for it, is for triage to decide.

## Open question: are epics the right grouping?

Before fixing this, decide whether epics earn their place, or whether a request's drafts should take the request itself as their `parent`.

For the request as parent:
- The request already is the grouping. It lists its drafts in `work_items` (spec user story 19). An epic created alongside it would hold the same set of items under a second name.
- The prompt already calls an epic "a grouping label: a title and a one-line outcome", and says no role working on a story reads it. A request carries more than that: the customer's own words, the questions and their answers.
- It needs no change to the backlog or the TUI. Any item may be a `parent`, and the TUI nests items under their parent whatever its type. Only the prompt would change.
- Drafts would be traceable to their request in both directions.

For keeping epics:
- An epic can collect work from several requests, or work captured directly rather than through a request. A request only ever groups what it drafted.
- An epic can outlive the request that started it, while further requests add to the same body of work.
- The prompts and examples already use epics. The glossary lists epic as a kind of work item but does not define it.

If requests become the parent:
- `parent` would name either a request or an epic, and that mix needs a decision.
- `work_items` and `parent` would record the same link from either end. That duplication may be acceptable, or one of them could go.
