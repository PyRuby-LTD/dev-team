---
schema_version: 1
id: STORY-008
type: story
title: "Request analysis and answer the current human question"
parent: EPIC-003
state: proposed
authorisation: not-played
depends_on: ["STORY-006","STORY-007"]
owner: product-owner
---

# Request analysis and answer the current human question

As the customer, I want to start analysis and answer questions in the TUI so I can refine a feature without inadvertently playing it.

Actions use the validated controller contract. Save partial answers durably without resuming analysis, then explicitly submit against the current request/revision/content digest; show acknowledgement and refreshed state. Retain unsent input on a conflict where practical. This explicit-submit interaction is a proposal recorded in shared assumptions A4, not a confirmed customer preference.

## Acceptance criteria

- [automated] Given a valid captured unplayed item, when the customer requests analysis, then the owning analysis role becomes eligible without implementation or release authority. Evidence: TUI/controller integration test.
- [automated] Given a current human request, when a partial answer is saved, then it survives reopening without resuming analysis; when a complete response is explicitly submitted, then the answer and decision are persisted once and the configured named transition resumes analysis. Evidence: partial-save/reopen and submit integration trace.
- [automated] Given saved partial or complete draft answers, when no submit action occurs, then the human step remains waiting; submitting incomplete required answers or answers to closed/superseded request IDs is refused while preserving the saved draft. Evidence: draft-completeness and superseded-request fixtures.
- [automated] Given a submitted answer whose acknowledgement is lost, when the TUI reconnects and retries the same request, then it displays the accepted result without a duplicate transition; a competing changed answer is shown as a conflict. Evidence: acknowledgement-loss/reconnect fixture.
- [automated] Given double-submit or a stale view, when the answer action is repeated, then it either acknowledges the already accepted answer or reports a conflict without overwriting the current response or issuing another human request. Evidence: duplicate/stale UI fixtures.
- [automated] Given a read-only view, refresh or answered question, when the action completes, then no customer play or release decision is created. Evidence: authority regression test.
- [human] Given a conflict while answering, when the TUI reports it, then the customer can see why and recover their intended answer. Evidence: conflict walkthrough.

## Refinement and evidence

Source: [brief](../brief.md). Proposals and open questions: [scope](../scope.md). Reconcile with intended [architecture](../architecture.md), [qualities](../qualities.md) and [quality strategy](../quality-strategy.md) before play. These criteria specify future evidence, not completed tests. This is a proposed planning record, not an input compatible with the prototype runner.
