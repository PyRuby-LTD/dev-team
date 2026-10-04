---
schema_version: 1
id: STORY-003
type: story
title: "Preview and import legacy work without destroying originals"
parent: EPIC-001
state: proposed
authorisation: not-played
depends_on: ["STORY-001","STORY-002"]
owner: product-owner
---

# Preview and import legacy work without destroying originals

As the customer, I want to retain existing prototype work and evidence while moving to the authoritative Markdown model.

Provide a read-only preview and explicit apply step. Preserve source files and provenance; after import the legacy source is historical evidence only, not live state. Do not bulk-delete or run legacy work.

## Acceptance criteria

- [automated] Given legacy state.json and narrative/evidence files, when preview runs, then proposed mappings, collisions and uncertainties are reported without writes or agent dispatch. Evidence: preview report and filesystem comparison.
- [automated] Given a reviewed unambiguous mapping, when import is applied, then the Markdown item retains identity/provenance, meaningful history and evidence links while original files remain byte-for-byte unchanged. Evidence: import fixture and source checksums.
- [automated] Given an unknown stage, ID collision or legacy approval with unclear meaning, when import is attempted, then the affected item requires resolution and never becomes ready, played or released by inference. Evidence: blocked import fixtures.
- [automated] Given an already imported source, when import is repeated or restarted, then it creates no duplicate item or history entry; changed sources are reported for reconciliation. Evidence: idempotency/restart tests.

## Refinement and evidence

Source: [brief](../brief.md). Proposals and open questions: [scope](../scope.md). Reconcile with intended [architecture](../architecture.md), [qualities](../qualities.md) and [quality strategy](../quality-strategy.md) before play. These criteria specify future evidence, not completed tests. This is a proposed planning record, not an input compatible with the prototype runner.
