# Proposed scope and sequencing

Authority: [brief](brief.md). All epics and stories are proposed, not played and pending customer prioritisation. This document records product-owner proposals separately from customer decisions.

## Confirmed customer decisions

Markdown front matter alone owns work-item state, including questions, answers, decisions, execution metadata and history. Narrative stays in the body and large evidence can be linked. There is no authoritative DB or sibling state.json. Workflow steps own one agent or human role; agents decide whether to consult others. Python applies named validated outcome transitions. Analysis can repeatedly return to a human. Ready is not permission to play; release needs a separate customer decision. This commission is analysis/backlog only.

## Proposed first slice

Three detailed epics and ten stories cover capture → analysis → human answer → repeated analysis → ready → explicit play authorisation recorded at a delivery boundary. The slice offers a minimal TUI, durable recovery, self-contained current-directory launch and a non-destructive route from legacy records. It does not invoke the prototype delivery pipeline.

| Epic | Stories | Intended outcome |
|---|---|---|
| EPIC-001: front-matter backlog | STORY-001–003, STORY-010 | Valid durable records, safe migration and portable launch |
| EPIC-002: owned workflow and analysis loop | STORY-004–006 | Validated progression, durable questions and safe recovery |
| EPIC-003: minimal TUI and customer actions | STORY-007–009 | Visible work, answers and explicit play |

Suggested dependency sequence: STORY-001 → STORY-002; STORY-003 follows both. STORY-004 follows STORY-001; STORY-005 follows STORY-002/004; STORY-006 follows STORY-005. STORY-007 follows STORY-001/004; STORY-008 follows STORY-006/007; STORY-009 follows STORY-008. STORY-010 follows STORY-007 for portable TUI acceptance. Migration need not block workflow design, but is part of slice acceptance. No tasks are created at this stage.

### Story summary for the delivery plan

| Story | Concrete result |
|---|---|
| STORY-001 | Capture and validate linked Markdown work; capture never invokes an agent |
| STORY-002 | Preserve state with atomic writes, revision/content checks and a manual-edit protocol |
| STORY-003 | Preview and explicitly import legacy work without destroying originals |
| STORY-004 | Validate single-owner workflows with explicit customer Analyse and named outcomes |
| STORY-005 | Dispatch scoped analysis and persist repeated human questions/answers |
| STORY-006 | Recover stale/uncertain attempts; control runtime lifecycle and prove offline smoke |
| STORY-007 | Inspect hierarchy, state, owner, questions and evidence in the terminal |
| STORY-008 | Request analysis, save partial answers and explicitly submit current responses |
| STORY-009 | Verify explicit play with a fake/guarded successor; real delivery remains deferred |

Capturing an item does not authorise analysis or spend provider tokens. The captured step belongs to human:customer until an explicit Analyse action. The play demonstration does not promise operational implementation or delivery to staging. Platform lifecycle, permission separation and offline verification are integrated into existing stories rather than separate platform work items.

## Deferred themes and revisit triggers

- EPIC-004, GitHub/CI delivery: defer implementation, test/review execution and external integrations until the analysis/play boundary is demonstrated and customer prioritises delivery.
- EPIC-005, staging/user testing/release: defer deployment and release machinery until a delivery candidate exists and environment requirements are confirmed. Release remains an independent customer gate.
- EPIC-006, reusable product/sprint-zero/specialists: defer automated product bootstrapping and extension packaging until the first harness journey works and a next product supplies concrete reuse needs.

These are named epic themes with success criteria, deliberately without story decomposition.

## Product-owner proposals and assumptions — not customer decisions

These entries are kept here because this role is authorised to edit only its product artifacts; the delivery manager can incorporate them into shared assumptions without this role editing another owner's file.

- PO-A1: Start with one customer operating a selected workspace through a local terminal. Multiple independent controllers must still fail safely on conflicts. Owner: product owner, with architect. Revisit if shared remote operation or distinct user permissions are required.
- PO-A2: First-slice play records explicit authorisation and displays a delivery hand-off, without executing implementation. Owner: product owner. Revisit if the customer requires actual delivery before this slice is useful; that expands scope into EPIC-004.
- PO-A3: Capture supports epic/story/task/bug types, while this planning backlog decomposes only epics and stories. Owner: product owner with architect. Parent rules and runtime field names require schema design; do not invent inherited play permission.
- PO-A4: Legacy import is previewed and explicitly applied, preserving originals and provenance. Unknown stages or conflicting IDs require resolution, never a guessed ready/played state. Owner: architect with product owner. Revisit after examining real legacy examples.
- PO-A5: TUI is the initial human request surface; reopening shows the same request, not a new notification. Owner: product owner. External messages are deferred; revisit if the customer needs another channel.
- PO-A6: A changed item after play requires a new authorisation decision before delivery consumes it. Owner: product owner with architect/quality lead. Exact revision and invalidation rules need agreement.
- PO-A7: Human reconciliation is appropriate when restart cannot establish whether an agent attempt finished. Owner: architect with quality lead. Confirm the recovery contract before implementation; do not promise exactly-once external agent execution.

Open questions for refinement: architect owns schema/transition version compatibility, atomic write/conflict and attempt identity design; quality lead owns fault-injection evidence and accessibility review; product owner owns whether the proposed hand-off is a useful first release and the explicit partial-save/submit interaction. Platform owns engine capability verification, cancellation/timeout policy, evidence retention and installation support. Audience volume, performance targets, auth needs and hosting remain unconfirmed. No invented deadline, budget, storage branch, framework or agent retry limit is a customer decision. These questions do not block drafting; see the shared [assumptions](assumptions.md) and owned questions in [engagement](engagement.md).

## Planning schema and readiness

Review refinements: workflow pinning/migration belongs to STORY-004; consistent adapter context and enforced analysis-only preflight to STORY-005; lifecycle and fixture-only installed-resource smoke to STORY-006. That minimal packaging check is proposed first-slice scope and gates a live pilot; broad distribution/release packaging is deferred. No real-engine compatibility is claimed by offline checks. STORY-002 explicitly covers body-only manual edits through pause/edit/validate/resume; STORY-008 preserves partial answers until deliberate submission.

Dependency completion has a proposed runtime contract in architecture.md: direct prerequisites gate play/delivery, not refinement, and require a validated verified-completion record with evidence bound to current material scope and a successful workflow completion state. Parent/child relationships confer neither completion nor authorisation. STORY-004 defines the contract; STORY-009 verifies both satisfied and unsatisfied prerequisite fixtures. Unsupported or unresolved evidence fails closed. This is a technical proposal, not completion or authorisation for any planning item.

Each epic/story has schema_version: 1, identity, type, title, state: proposed, authorisation: not-played and dependency IDs. Stories identify their parent; epics declare detailed/deferred. This is a proposed planning format, not a runtime schema or input compatible with today's state.json runner. The optional owner denotes artifact ownership, not a runtime workflow binding. No fabricated workflow reference is assigned.

All story criteria are Given/When/Then with automated or human evidence. Evidence specified is future acceptance evidence, not a claim that tests ran. Before play, reconcile [architecture](architecture.md), [qualities](qualities.md), [quality strategy](quality-strategy.md) and [platform](platform.md) with this backlog, resolve material open questions, and obtain customer prioritisation and explicit play. These intended shared files may still be under concurrent drafting.
