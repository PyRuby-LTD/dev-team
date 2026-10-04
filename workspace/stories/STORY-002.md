---
schema_version: 1
id: STORY-002
type: story
title: Preserve authoritative state across writes and conflicts
parent: EPIC-001
state: implemented
authorisation: played
depends_on:
- STORY-001
owner: product-owner
x-session:
  customer_instruction: play story ./workspace/stories/STORY-002.md
  date: '2026-10-04'
  mode: controlled-implementation
  evidence: ../evidence/STORY-002.md
  verification: automated-checks-passed
revision: 1
history:
- id: 4daed7ae-b9c2-4b69-aa00-7b6d3752dcc0
  actor: controlled-session
  at: '2026-10-04T10:42:19.812306+00:00'
  event: update
  before_revision: 0
  after_revision: 1
  before_state: proposed
  after_state: implemented
  source_digest: af171815508784bf20ce328adc33610075f577f8137f37108184e7c8fc8604ba
  evidence:
  - ../evidence/STORY-002.md
---

# Preserve authoritative state across writes and conflicts

As the customer, I want updates and restarts to preserve my backlog so a crash or competing edit cannot silently lose decisions.

Propose revision-and-content-digest checked atomic updates with execution status distinct from workflow progress. Architect chooses the mechanism; no DB or authoritative sibling JSON is introduced. Supported manual edits pause managed writes for that item, then resume through validation; universal protection against an uncooperative concurrent editor is not promised.

## Acceptance criteria

- [automated] Given a valid record, when an update is interrupted before or during replacement, then reopening yields the previous or complete new valid record, never partial front matter. Evidence: write fault-injection suite.
- [automated] Given two managed updates based on the same revision and content digest, when both attempt to commit, then one succeeds and the stale one reports conflict without overwriting history or narrative. Evidence: concurrent update fixture.
- [automated] Given a paused item whose body or metadata was manually edited without incrementing revision, when resume validates its content digest, then the change is recorded with a new revision and old responses are invalidated; malformed edits remain visibly blocked without overwrite. Evidence: supported manual-edit fixtures.
- [automated] Given detected edits outside the supported pause/edit/resume protocol, when a managed update is attempted, then it reports a conflict and explains reconciliation rather than silently merging. Evidence: digest-conflict fixture; documented remaining editor race limitation.
- [automated] Given linked evidence and an execution failure, when the record is reopened, then state is reconstructed from Markdown alone and failure is distinguishable from a completed workflow transition. Evidence: persistence/restart fixture.
- [automated] Given a rejected malformed update, when saving fails, then the last valid content and unrelated fields remain intact. Evidence: before/after content comparison.

## Refinement and evidence

Source: [brief](../brief.md). Proposals and open questions: [scope](../scope.md). Reconcile with intended [architecture](../architecture.md), [qualities](../qualities.md) and [quality strategy](../quality-strategy.md) before play. Implemented in a controlled session after the explicit customer play instruction recorded in front matter. [Evidence](../evidence/STORY-002.md) maps the automated results and documents the supported filesystem and manual-edit boundary. [ADR-002](../decisions/ADR-002.md) records the storage design. This remains a planning record, not input to the prototype runner or proof of customer acceptance or release.
