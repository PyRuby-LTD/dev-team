---
schema_version: 1
id: EPIC-005
type: epic
title: "Staging, user testing and separately controlled release"
state: proposed
authorisation: not-played
detail: deferred
depends_on: ["EPIC-004"]
owner: product-owner
---

# Staging, user testing and separately controlled release

Named later theme: make candidates available in staging for customer testing and require explicit release authority. Environment, deployment and rollback details need platform analysis. Revisit when a delivery candidate and customer environment constraints exist.

## Success criteria

- [human] Given a staged candidate, when the customer tests it, then acceptance or requested changes are recorded against that candidate. Evidence: future user-test record.
- [automated] Given a candidate with passing tests but no release authorisation, when automation runs, then no release occurs. Evidence: future release-gate integration test.

Source: [brief](../brief.md). Scope, assumptions and revisit triggers: [scope](../scope.md). Intended design/evidence contracts: [architecture](../architecture.md), [qualities](../qualities.md), [quality strategy](../quality-strategy.md). These are planning records, not runnable prototype inputs; criteria describe future evidence.
