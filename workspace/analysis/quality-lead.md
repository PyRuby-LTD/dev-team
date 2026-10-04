# Quality-lead analysis

Owner: quality lead. Date: 2026-10-02. Status: analysis only; backlog unplayed.

## Findings from current code

Read the team charters, `.claude/skills/quality-lead/SKILL.md`, configured
workspace, brief, engagement and assumptions, plus all runtime modules under
`devteam/`, README, role configuration and intake/investigate prompts. This is
static inspection, not runtime verification. No implementation pipeline or
test suite was invoked. No `tests/` directory was present in the inspected tree.

| Source | Observed behavior | Acceptance implication |
|---|---|---|
| `devteam/workitem.py`: WorkItem, save, decision | Loads/saves sibling `state.json` directly; stage JSON is parsed but not structurally validated; history is mutable data. | Markdown authority, schema validation and atomic/conflict-safe persistence are new work (V1, V5, V7), not existing guarantees. |
| `devteam/pipeline.py`: STAGES, step, ADVANCE | Four hard-coded agent stages; outcomes handled with permissive dictionary access; no correlated response identity/owner/revision validation. | Declarative owner-only workflow and validated transition contract need negative acceptance cases (V2, V5). |
| `devteam/pipeline.py`: step; `devteam/engines.py`: run | Marks running before synchronous subprocess invocation; dispatch/acknowledgement ambiguity has no reconciliation protocol. | Restart must distinguish pending, failed and uncertain execution; rerun is not automatically safe (V6). |
| `devteam/cli.py`: cmd_run, cmd_decide | Runs one item through ready stages; human decisions are accepted without checking current gate. Resume follows edits to request text; revise sets implementation directly. | No durable structured question loop or explicit implementation permission guarantee; legacy commands are not the new acceptance path (V3, V4, V8). |
| `devteam/cli.py`: status/show | Snapshot CLI output, no reconnectable TUI or scheduler across items. | TUI reconstruction and nonblocking human waiting need integrated evidence (V8–V10). |

`config.py` already resolves a configured workspace and role/engine configuration;
these are useful seams to evaluate, not proof that new ownership or persistence
contracts are implemented. The current README's broad “nothing is promoted
automatically” wording does not establish a separate play decision once legacy
`run` starts. The new contract must be tested explicitly.

## Acceptance gaps to reconcile with emerging stories

Initial inspection preceded the backlog. Follow-up review read plan, engagement,
scope, architecture, ADR-001 and all nine stories and six epics as they appeared.
The general review targets below are followed by concrete owner corrections.
This is a concurrent drafting snapshot, not final acceptance of later revisions.

| Story area | Gap that a happy-path criterion would miss | Proposed owner / checks |
|---|---|---|
| Capture and schema | Duplicate IDs/keys, relationship integrity, unsupported version, narrative preservation and stale legacy state competing with Markdown. | architect + product owner; V1 |
| Workflow engine | Exactly one owner including human steps; invalid definition versus invalid response; versioned response correlation; consultative agents cannot independently advance the item. | architect; V2 |
| Human interaction | Stable question IDs, partial drafts, explicit submit policy, revised answers, repeated rounds, stale/closed requests and durable recovery. | product owner; V3, V5 |
| Readiness and play | A ready item remains unplayed through answers/restart; direct commands cannot bypass the boundary; scope of permission after item edits; release remains separate. | product owner + architect; V4 |
| Response/recovery | Duplicate acknowledgement loss differs from conflicting response reuse; persist-before-dispatch does not prove exactly-once execution. | architect + platform engineer; V5, V6 |
| Persistence/manual edits | Rename is not concurrency control; body-only edits must be detected; unsupported uncoordinated editor writes need an explicit policy. | architect + platform engineer; V7 |
| Scheduler | A human-waiting item does not monopolise the scheduler; invalid/failed items do not halt unrelated eligible work; repeated ticks do not spawn duplicates. | architect; V8 |
| Minimal TUI | Reconnect derives truth from records, handles lost acknowledgements/stale commands, and explains uncertainty without silently retrying. | product owner + architect; V9, V10 |
| Evidence and pilot | “Tests pass” needs fixture/trace evidence; useful question quality requires a human; live engine compatibility is a separate pilot gate. | quality lead + platform engineer; V1–V10 |

## Owned questions and proposals

These are unconfirmed proposals. Only the two quality documents are in this
role's write scope, so delivery manager should consolidate relevant additions
into the shared assumptions/questions registers without treating them as agreed.
Existing Q2/Q3/Q4/Q5 and A1/A4/A5 remain their source entries.

| ID | Proposed answer / unresolved decision | Decision owner | What would change acceptance |
|---|---|---|---|
| QL1 | Require workflow/run identity and a full-document concurrency token on responses; use trusted invocation context for ownership, not a self-declared role string. Exact schema remains open. | architect | Different correlation/authentication design changes V2/V5 fixtures but must still reject wrong-owner/stale responses. |
| QL2 | Explicit submit of persisted required answers (existing Q4/A4); draft save never resumes. Define whether answers can change after submit. | product owner | Automatic completion or post-submit correction needs explicit semantics and amended V3/V9 checks. |
| QL3 | Treat possibly launched work as uncertain until reconciled; prohibit blind retries without an adapter idempotency guarantee. Define who may reconcile and what evidence permits retry. | architect + platform engineer | A proven adapter query/deduplication mechanism can automate recovery; otherwise human disposition remains a gate in V6. |
| QL4 | Support one local coordinator initially (Q2/A1), but specify a safe manual-edit protocol. A plain hash-check followed by replace is insufficient against an arbitrary concurrent editor. | architect + platform engineer | Multi-host writers or unrestricted active editing require stronger coordination/recovery and expanded V7 scope. |
| QL5 | Proposed first slice records explicit play permission without launching the legacy implementation runner. Define whether material edits invalidate previously recorded permission. | product owner + architect | If execution is selected into scope, add execution authority checks and dependencies before play; approval must not silently cover changed work. |
| QL6 | Define process-crash versus power-loss durability and supported filesystem behavior; avoid claiming both from process interruption tests. | platform engineer | Stronger durability commitment requires additional persistence evidence and supported-platform checks. |
| QL7 | Fake adapters first (A5); retain both automated traces and a customer usability/analysis review. Choose the live pilot profile under Q3 and constraints under Q5. | quality lead coordinates; platform engineer/customer select profile and limits | Live compatibility, real usage constraints or a chosen human reviewer change pilot evidence, not the authority invariants. |

Quality lead owns checking that these decisions become observable criteria and
that final stories cite automated versus human evidence. Product owner owns
user-facing policy; architect owns protocol/concurrency design; platform owns
operational guarantees; delivery manager routes unresolved cross-role decisions.
These questions do not block creating an unplayed draft backlog. They must be
resolved or explicitly scoped before the affected stories are selected to play.

## Handoff

### Emerging backlog review and owner corrections

All nine stories and six epics inspected have `state: proposed` and
`authorisation: not-played`. Their criteria distinguish automated/human evidence.
STORY-006 correctly rejects blind retries and duplicate transitions; STORY-009
correctly records revision-scoped play without real implementation and prevents
inherited child authority. These align with the requested boundaries.

Original critical findings (disposition in the final validation note below):

- **C1 — architect, product owner:** architecture's flow gives `captured` an
  agent owner and `begin-analysis` outcome without an explicit customer-intent
  guard. STORY-008 has the positive request-analysis action, but STORY-001/005
  do not prove capture and scheduler scans cannot dispatch. Add the durable
  explicit analyse gate and V0 negative/replay cases to the contract and stories.
  Team proposes this explicit analyse gate for the first slice. The customer's
  latest commission authorises analysis/backlog creation, not a new policy answer.
- **C2 — architect:** architecture says attempted play should explain an
  unsupported boundary and describes a future play outcome, whereas plan step 10
  and STORY-009 require recording explicit authorisation now and verifying the
  boundary with a fake/guarded successor. Align architecture/ADR to that limited
  handoff. No real implementation or legacy runner invocation is required.

Original acceptance omissions (disposition below; remaining refinement is owned
by product owner before affected stories are played):

- **G1 — product owner, STORY-002:** two revision-aware updates do not cover a
  manual body edit without revision change. Architecture/ADR now propose
  pause/edit/validate/resume and acknowledge the uncooperative-editor race. Add
  that protocol, stale response invalidation and unsupported-edit diagnostics to
  acceptance rather than claiming blanket lost-update protection (V7).
- **G2 — product owner, STORY-005/008:** add saved partial/complete drafts that
  do not resume before explicit submit, completeness validation, repeated
  question IDs and superseded-request rejection (V3). Plan explicitly includes
  partial save; current story criteria focus on submitted answers.
- **G3 — product owner, STORY-007/008:** add actual TUI disconnect/reconnect and
  acknowledgement-loss scenarios, including stale pending actions. Refresh
  snapshots and controller restart alone do not prove this behavior (V9).
- **G4 — product owner/architect, STORY-005/006:** add wrong owner/item/workflow
  digest and reused response ID with a different payload. Architecture defines
  these checks; generic malformed/stale criteria do not enumerate them (V2/V5).

Suggested evidence mapping: STORY-001 → V0/V1; STORY-002 → V7;
STORY-003 → V0/V1 plus its explicit preview/import/source-preservation fixtures;
STORY-004 → V2/V4; STORY-005 → V2/V3/V8; STORY-006 → V5/V6;
STORY-007 → V1/V9/V10; STORY-008 → V0/V3/V5/V9/V10;
STORY-009 → V4/V5/V9/V10. Legacy-import evidence must include unchanged source
bytes, idempotent apply/restart and no inferred play/release, as STORY-003 states.

QL4's editing protocol and QL5's permission invalidation now have explicit
architecture/product proposals; they remain proposed choices, not missing design.
The remaining task is agreement and matching acceptance evidence. QL1 likewise
has a concrete response-envelope proposal in architecture. No owner correction
was applied directly to another role's artifact.

### Final validation note

The closing read confirms C1 is addressed in architecture and STORY-001/004/005:
capture waits for explicit customer Analyse intent. C2 is addressed in
architecture and STORY-009: play is recorded with delivery held, verified only
through a fake/guarded successor; no legacy implementation is invoked.
STORY-002 now includes the supported manual-edit/body-digest protocol (G1).
STORY-008 now explicitly saves partial answers across reopening without resuming
and requires complete explicit submission; this addresses the core G2 omission.
STORY-005 adds role/product context and permission-denial criteria, and STORY-006
adds process lifecycle, coordinator ownership and installed-resource checks.
The strategy includes the corresponding evidence obligations.

The coordinating delivery manager reports that separate challenger/coherence review is complete and
the product owner is incorporating remaining draft-answer and related criteria.
Residual G2–G4 cases belong to final owner reconciliation, not another drafting
round here. The architect's qualities.md was not present at the
closing read and is being created; no review of that artifact is claimed.
This handoff verifies document alignment by static inspection, not implemented
behavior. All tests and live-pilot evidence remain future work. No runtime
correctness, live permissions or performance result is claimed.

Final consolidated dispositions are maintained in
[analysis/review.md](review.md). C1/C2 and
G1–G4 above preserve the findings snapshot, not a claim that owner updates remain
outstanding. Consult that review for final closure and any remaining actions.

Produced the verification plan and this acceptance-gap report only. No external
writes, implementation, test scripts or work-item state changes were made.
Next, product owner and architect should reconcile emerging stories/design with
the acceptance matrix; delivery manager should collect decisions and preserve
customer prioritisation and the unplayed boundary. No evidence of implemented
correctness is claimed by completion of these analysis documents.
