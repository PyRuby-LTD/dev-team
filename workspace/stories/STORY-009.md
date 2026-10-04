---
schema_version: 1
id: STORY-009
type: story
title: "Explicitly play a ready revision at the delivery boundary"
parent: EPIC-003
state: proposed
authorisation: not-played
depends_on: ["STORY-008"]
owner: product-owner
---

# Explicitly play a ready revision at the delivery boundary

As the customer, I want to explicitly authorise selected ready work so I control implementation priority and later communication with users.

Provide a separate play action identifying the item and revision/content digest and persisting the customer decision. Proposed first-slice boundary: verify the action using a fake or guarded successor and display authorised work awaiting delivery capability, with no implementation execution or promise of operational delivery to staging. Real delivery remains disabled until its later capability exists. Release is independently gated in the deferred delivery journey. Parent play never silently authorises children.

Proposed dependency semantics follow architecture.md: direct dependencies gate play/delivery, not refinement. A prerequisite needs a validated verified-completion record, evidence and current material-scope digest plus a successful workflow completion state. Parent status and child counts cannot substitute. Missing or stale evidence blocks play. These rules are proposals for implementation review, not completion claims for this backlog.

## Acceptance criteria

- [automated] Given a ready unplayed item, when time passes, analysis completes or the TUI refreshes, then it stays unplayed. Evidence: ready-boundary regression test.
- [automated] Given a ready current revision, when the customer explicitly plays it, then one durable authorisation decision identifies that revision and the TUI shows the delivery hand-off; no prototype pipeline, agent implementation or release is invoked. Evidence: play integration trace with dispatch assertions.
- [automated] Given a not-ready item, unmet prerequisite or stale revision, when play is requested, then it is refused with a reason and leaves authorisation unchanged. Evidence: negative play fixtures.
- [automated] Given direct prerequisites with valid verified-completion records and evidence bound to their current material scope, when the customer plays a ready item, then those prerequisites permit the guarded hand-off; missing, stale, failed, cancelled or merely ready prerequisites refuse play with specific reasons. Evidence: positive/negative dependency fixtures, including an epic with completed children but no accepted epic outcome.
- [automated] Given an unmet prerequisite or a parent with its own dependencies, when a child is captured or analysed, then refinement may proceed without inherited authorisation; only explicit dependencies on that child gate its eventual play. Evidence: refinement-versus-execution and non-inheritance fixtures.
- [automated] Given a previously accepted play request, when repeated, then it creates no duplicate decision; given a subsequent material item change, when delivery eligibility is checked, then earlier play cannot authorise the changed revision. Evidence: replay and revision invalidation fixtures.
- [automated] Given an epic and unplayed child stories, when the epic is played, then child authorisation and release authority remain unchanged. Evidence: hierarchy authority fixture.
- [human] Given ready and explicitly played items, when the customer reviews their terminal views, then the meaning of the hand-off and separate release gate is clear. Evidence: customer boundary walkthrough.

## Refinement and evidence

Source: [brief](../brief.md). Proposals and open questions: [scope](../scope.md). Reconcile with intended [architecture](../architecture.md), [qualities](../qualities.md) and [quality strategy](../quality-strategy.md) before play. These criteria specify future evidence, not completed tests. This is a proposed planning record, not an input compatible with the prototype runner.
