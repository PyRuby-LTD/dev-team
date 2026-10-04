# Challenger and coherence review

Date: 2026-10-02. Owner: delivery manager records review dispositions; content
owners resolved their own artifacts. Review uses `../../.claude/agents/challenger.md`
and `../../.claude/agents/coherence.md`, with quality-lead acceptance review.

## Scope and evidence

Reviewed the customer brief, proposed scope, architecture, platform and quality
analysis, and six epics/nine stories. This is a review of planning artifacts,
not execution evidence. Role reports preserve findings from intermediate drafts;
this file records their consolidated disposition at handoff.

## Findings and dispositions

| Finding | Owning role | Disposition |
|---|---|---|
| Architecture treated first-slice play as unavailable, while STORY-009 recorded authorisation at a held delivery boundary. | architect / product owner | Align to the product proposal: record explicit scoped play, hold delivery unavailable, never fall back to the old runner. Customer can still change first-slice breadth (Q8). |
| Initial example could automatically dispatch analysis from captured backlog. | architect / product owner | Propose a human-owned captured step and explicit analyse action; capture alone does not dispatch. This is a team-proposed first-slice control, not a newly received customer instruction. |
| Acceptance criteria omitted manual body-only edits, partial draft answers, invocation context and lifecycle boundaries described elsewhere. | product owner / quality lead | Consolidate these into STORY-002 and STORY-004 through STORY-008; evidence belongs in canonical stories and the quality matrix. |
| Dependency satisfaction was mentioned without a defined predicate. | architect / product owner | Specify proposed verified-completion semantics for execution/play; allow refinement before dependencies complete. Hierarchy must not silently confer authorisation. |
| Stories linked a missing qualities document. | architect | Add qualities.md with measurable correctness invariants and explicitly unconfirmed capacity/performance targets. |
| Platform analysis contained a second set of fenced pseudo-backlog records and alternate state names. | platform engineer | Removed them; retain a requirements handoff table mapped into PO-owned canonical items. |
| Prototype role/model configuration and worktrees could be mistaken for verified permission/isolation guarantees. | platform engineer / architect | Require verified adapter context and capability boundaries before live analysis; worktrees alone are not a sandbox. |

## Confirmed strengths

- All canonical epic/story records are proposed and not played.
- Item front matter is the sole work-item state authority; no database or sibling
  authoritative state file is introduced.
- Workflow contracts require exactly one owner and named outcomes; they do not
  prescribe collaborators. Consultations remain the owning agent's choice.
- Repeated analysis/human loops, durable requests, stale/duplicate responses and
  uncertain restart handling are represented.
- Recovery does not claim exactly-once external agent effects.
- Deferred epics retain GitHub delivery, test/review/automation, staging/UAT,
  separate release, walking skeletons and specialist/product reuse.
- Every story identifies future automated/human evidence in Given/When/Then form.
- Storage, live-engine choice, concurrency, editing and scope proposals remain
  distinguishable from confirmed customer decisions.

## Handoff boundary

Open questions and assumptions remain in engagement.md and assumptions.md, with
technical alternatives in the individual role reports. They do not prevent
delivery of this unplayed backlog. Resolve material choices before the affected
story is selected and played. No implementation or production readiness is
claimed by this review.

The delivery manager validates YAML front matter, unique IDs, parent/dependency
references, dependency cycles, planning authorisation and local Markdown links
before handoff. These document checks do not validate the future controller.

## Final reconciliation and document checks

Completed 2026-10-02 by the coordinating agent after delegated usage limits
interrupted final role follow-up. Preserved the role drafts and completed the
following local refinements:

- Unified the dependency proposal across architecture, scope and STORY-004/009;
  fixtures cover verified, stale and unsatisfied prerequisites.
- Added wrong-owner/workflow response checks, conflicting response-ID reuse,
  draft completeness/superseded requests and TUI acknowledgement-loss/reconnect
  criteria to STORY-005 through STORY-008.
- Removed an accidental acceptance dependency from STORY-006 on future
  STORY-009: its installed smoke covers controller/recovery first; guarded play
  is added by the later story.
- Distinguished the team's proposed explicit Analyse gate from actual customer
  corrections. The customer confirmed owner-only workflow and front-matter
  authority, not a newly invented operational instruction.
- Completed qualities.md links and retained outstanding customer choices as
  proposals/questions rather than marking items approved or played.

Validation passed: 15 canonical records across 32 Markdown documents; 126 local
Markdown links resolve; YAML keys/IDs are unique; parent/dependency references
are valid; the dependency graph is acyclic; acceptance criteria include
Given/When/Then and evidence; every epic/story remains proposed and not played.
No application implementation, agent delivery runs or external publication were
performed. Future acceptance tests described in this workspace have not run.
