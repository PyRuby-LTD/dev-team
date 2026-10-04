---
schema_version: 1
id: EPIC-003
type: epic
title: "Minimal terminal visibility and customer actions"
state: proposed
authorisation: not-played
detail: detailed
depends_on: ["EPIC-002"]
owner: product-owner
---

# Minimal terminal visibility and customer actions

Let the customer see work and ownership, answer questions and explicitly authorise a ready item. First-slice play ends at a visible delivery hand-off, not pipeline execution. Stories: STORY-007, STORY-008, STORY-009.

## Success criteria

- [human] Given a workspace with proposed, analysing, waiting, failed and ready work, when the customer inspects it, then the next action and distinction between ready and played are clear. Evidence: recorded walkthrough and customer review.
- [automated] Given ready unplayed work, when the TUI refreshes or an answer is submitted, then play remains absent until the explicit action. Evidence: TUI/controller integration trace.

Source: [brief](../brief.md). Scope, assumptions and revisit triggers: [scope](../scope.md). Intended design/evidence contracts: [architecture](../architecture.md), [qualities](../qualities.md), [quality strategy](../quality-strategy.md). These are planning records, not runnable prototype inputs; criteria describe future evidence.
