# Delivery-team harness engagement

This workspace is the product analysis for developing the reusable team harness
itself. It is selected by `../config/workspace`. Planning artifacts do not grant
permission to execute the backlog.

## Start here

- [Brief](brief.md): verbatim customer messages and the agreed interpretation.
- [Problem](problem.md) and [capabilities](capabilities.md): intended outcomes.
- [Scope](scope.md): proposed first slice and explicit deferrals.
- [Plan](plan.md): sequenced stories and an end-to-end acceptance scenario.
- [Portable launch story](stories/STORY-010.md): self-contained team resources and current-directory product selection; specification only.
- [Engagement](engagement.md): role contributions and owned open questions.
- [Assumptions](assumptions.md): proposed defaults, not customer facts.
- [Architecture](architecture.md) and [decision](decisions/ADR-001.md): record and
  workflow contracts.
- [Quality attributes](qualities.md): proposed measurable correctness invariants.
- [Platform](platform.md): operating the harness and the boundary with products.
- [Quality strategy](quality-strategy.md): required checks and customer review.
- [Review](analysis/review.md): challenger/coherence review and dispositions.

## Backlog conventions

STORY-001 and STORY-002 have been explicitly played and implemented in controlled
sessions; their front matter and [capture evidence](evidence/STORY-001.md) and
[persistence evidence](evidence/STORY-002.md) record the results. Other stories
retain their existing status. The `devteam backlog` commands can capture, validate,
inspect and safely update these records without invoking agents. See the
[planning schema](../docs/backlog-schema-v1.md); runtime workflow execution is
still deferred.

Epics live in `epics/`; first-slice stories live in `stories/`. Each work item has
YAML front matter with its stable ID, type, title, relationships and planning
state. The initial records were proposed and not played. The body records intent,
scope and acceptance criteria. There is no independent authoritative state file
or database. The proposed loader must preserve this human-written content.

The metadata follows the version-one planning contract. The legacy delivery
pipeline does not load these documents; do not mistake a Markdown story for an
already-dispatchable legacy ITEM directory.

The summaries in this index, scope and plan are navigation, not additional item
state stores. Item front matter remains authoritative if summaries become stale.
The proposed implementation must keep all item-specific state in those records;
shared workflow definitions and linked evidence are separate resources.
