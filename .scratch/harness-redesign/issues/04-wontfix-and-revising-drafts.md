# 04: Won't fix, and revising a request's drafts

**What to build:** The default workflow gains a terminal `wontfix` step reached from `captured` and `ready` by a customer outcome; the item stays in the backlog as a record. When the customer chooses `revise` on a request, the product owner updates existing drafts with `dev-team backlog update`, and takes any draft no longer needed out of the request's work items, saying why. It never deletes or closes a draft itself; the customer marks it won't fix.

**Blocked by:** 01

**Status:** ready-for-agent

- [x] A journey test revises a request: a stub product owner updates one draft and drops another from the request's work items; the customer records `wontfix` on the dropped draft, which stays in the backlog at `wontfix` with its history
- [x] The request analysis prompt covers revising drafts this way, drafted for the author to review
- [x] Nothing in the harness offers deleting a work item
