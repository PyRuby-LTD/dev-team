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
