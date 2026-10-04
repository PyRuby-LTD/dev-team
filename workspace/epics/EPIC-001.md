---
schema_version: 1
id: EPIC-001
type: epic
title: "Authoritative front-matter backlog"
state: proposed
authorisation: not-played
detail: detailed
depends_on: []
owner: product-owner
---

# Authoritative front-matter backlog

Let the customer capture and recover work with one authoritative record. Includes schema validation, safe writes, non-destructive legacy migration and self-contained launch against the current product directory; excludes choosing a storage branch or retaining live JSON authority. Stories: STORY-001, STORY-002, STORY-003, [STORY-010](../stories/STORY-010.md).

## Success criteria

- [automated] Given valid epic/story/task/bug records, when reopened, then identity, hierarchy and state come from Markdown front matter alone. Evidence: round-trip and malformed-record fixtures.
- [automated] Given interrupted writes or conflicting legacy imports, when recovery/import is attempted, then valid originals survive and no authorisation is inferred. Evidence: failure-injection results and import report.

Source: [brief](../brief.md). Scope, assumptions and revisit triggers: [scope](../scope.md). Intended design/evidence contracts: [architecture](../architecture.md), [qualities](../qualities.md), [quality strategy](../quality-strategy.md). These are planning records, not runnable prototype inputs; criteria describe future evidence.
