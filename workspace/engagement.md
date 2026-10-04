# Engagement

Owner: delivery manager. Date: 2026-10-02.

## Commission and authority

Analyse the agreed workflow/controller proposal and create epics and stories
using the existing team definitions. The harness itself is this engagement's
product. No implementation, external publication, deployment or agent execution
of the resulting stories is authorised by this commission.

The customer's latest correction overrides earlier assistant proposals: one
owner per step, no workflow collaborator declaration; Markdown front matter is
authoritative, not sibling JSON state or a local database. GitHub is critical;
Linear is optional and not part of the proposed first slice.

## Team running order

1. Delivery manager captures the customer brief and boundaries.
2. Product owner proposes capabilities, first-slice epics and stories.
3. Architect and platform engineer analyse contracts and operating constraints
   in parallel, recording proposals rather than inventing customer requirements.
4. Quality lead checks acceptance evidence; challenger/coherence review checks
   the combined handoff for contradictions and missing requirements.
5. Delivery manager consolidates the sequence, owned questions and assumptions.

The role definitions come from `../team/`; associated local skills explain their
artifact responsibilities. Delegated role analysis is conducted in this session,
not through the legacy implementation pipeline.

## Customer decisions already recorded

- Python controls a basic state machine over work items.
- The configured workflow maps named responses to target steps.
- A step belongs to one agent role or human role.
- Agent owners decide for themselves whether to consult other roles.
- Questions can cause repeated analysis -> human -> analysis transitions.
- Readiness does not authorise implementation; release remains separately chosen.
- A TUI exposes work items, human requests and delivery progress.
- Work-item persistence must not require a local database.

## Open questions to resolve before dependent work is played

| ID | Question | Owner | Impact / proposed default |
|---|---|---|---|
| Q1 | Where should each product's planning documents be versioned: its ordinary branch, a metadata branch, or a separate repository? | platform engineer | Keep the existing configured workspace for this analysis; do not create a branch/repository or decide publication policy yet. |
| Q2 | Should v1 coordinate a single local operator/process per product, or must multiple machines write concurrently? | architect | Propose one local coordinator with conflicting edits detected; multi-host coordination changes the design. |
| Q3 | Which installed/authenticated coding engine and role should perform the first live analysis run? | platform engineer | Use fake adapters for acceptance checks; require a verified local engine profile for the live pilot. |
| Q4 | Should answering the final outstanding question resume analysis immediately, or require an explicit submit/continue action? | product owner | Propose explicit submit so a partial answer cannot trigger unintended work. |
| Q5 | What deadline, run-cost ceiling, backlog volume or response-time target would constrain this first slice? | delivery manager | None supplied. Do not claim a budget, capacity or numeric performance promise. |
| Q6 | Is pause/edit/validate/resume acceptable for manual document edits, and which local OS/filesystem must the first pilot support? | architect / platform engineer | Proposed atomic-write guarantees depend on the filesystem and cooperating writers. |
| Q7 | What product data may reach the selected provider, and which diagnostics/retention are needed? | platform engineer | Propose minimal nonsecret evidence; timeout and provider capability policies must be selected before live operation. |
| Q8 | Is a first slice that records play but holds delivery unavailable useful, or must real implementation be included? | product owner | STORY-009 proposes the held hand-off; actual implementation would bring EPIC-004 into scope. |

These are owned questions, not blockers to creating this draft backlog. Any that
remain unresolved at implementation selection must be surfaced with the affected
story; passing time is not customer approval of the proposed default.

## Role handoff

- Product owner: problem, capabilities, scope, six epics and ten first-slice
  stories with acceptance evidence.
- Architect: front-matter/workflow/response contracts, local coordination and
  restart proposal, quality attributes and ADR-001.
- Platform engineer: local bootstrap, lifecycle, permission, evidence and later
  GitHub/deployment considerations, with a candidate-requirements handoff.
- Quality lead: V0–V10 verification matrix and story-level acceptance review.
- Challenger/coherence reviewer: cross-artifact and scope review; dispositions
  in [analysis/review.md](analysis/review.md).
- Delivery manager: verbatim brief, assumptions, owned questions, consolidated
  dependency sequence and document validation.

The proposed first slice is EPIC-001 through EPIC-003 (STORY-001 through
STORY-010). EPIC-004 through EPIC-006 preserve later scope. These references are
navigation summaries, not additional sources of work-item state or priority.
