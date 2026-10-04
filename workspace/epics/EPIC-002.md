---
schema_version: 1
id: EPIC-002
type: epic
title: "Owner-only workflow and repeated analysis"
state: proposed
authorisation: not-played
detail: detailed
depends_on: ["EPIC-001"]
owner: product-owner
---

# Owner-only workflow and repeated analysis

Let the customer receive meaningful questions and reach ready work without losing control of play. Includes named outcomes, role validation, durable human waits and recovery. The owning agent may consult by its own choice; workflow definitions do not list collaborators. Stories: STORY-004, STORY-005, STORY-006.

## Success criteria

- [automated] Given analysis requires two clarification rounds, when matching answers arrive, then analysis repeats and reaches ready without play. Evidence: deterministic agent-double journey trace.
- [automated] Given duplicate/stale responses and a restart, when processing continues, then no duplicate transition or human request occurs and uncertainty is visible. Evidence: restart/replay fixtures.

Source: [brief](../brief.md). Scope, assumptions and revisit triggers: [scope](../scope.md). Intended design/evidence contracts: [architecture](../architecture.md), [qualities](../qualities.md), [quality strategy](../quality-strategy.md). These are planning records, not runnable prototype inputs; criteria describe future evidence.
