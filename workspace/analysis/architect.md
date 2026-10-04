# Architect analysis report

Status: analysis complete; proposals awaiting consolidation/customer decisions;
all suggested work unplayed and pending customer prioritisation. No agents,
implementation pipeline or external mutations were invoked.

Read `workspace/brief.md`, `team/README.md`, `team/architect.md`, the architect
skill, `config/workspace`, all current `devteam/*.py` modules and
`config/roles.toml`. Inspected role/prompt file names, not their contents. The
workspace resolves to this repository's `workspace/`. Git status was unavailable
because this directory is not a Git repository; no Git operations were performed.

## Conclusions for backlog authors

The prototype provides useful Python/workspace/engine seams but cannot run the
proposed records. Its hard-coded analysis-to-implementation path violates the
desired first-slice boundary. See `../architecture.md` for contracts and
`../decisions/ADR-001.md` for confirmed constraints versus proposed mechanics.

These are architectural story proposals for the product owner/delivery manager,
not separately authoritative work items. Only those roles should assign backlog
IDs, hierarchy, scope and priority in their owned files.

| Proposed story | Acceptance evidence to include |
| --- | --- |
| Define and validate Markdown item contract | Round trip all four item kinds and narrative; reject duplicate IDs/keys, bad hierarchy and unsupported versions; no sibling state authority |
| Preview and import legacy work (STORY-003) | Preview makes no writes; explicit apply preserves original checksums, identity/provenance/history/evidence; unresolved mappings cannot infer readiness/play/release; repeat/restart is idempotent |
| Commit guarded item changes | Two responses to one revision cannot both commit; manual body edit without revision bump is detected; interrupted write leaves a complete old/new file; supported edit-pause protocol documented |
| Interpret pinned owner-only workflows | Unknown owners/outcomes/targets and changed version digests fail visibly; agent cannot select target; existing items retain their pinned workflow |
| Deliver portable role/product context | Fake adapter receives charter, brief, item and allowed outcomes identically across engine bindings and relocated product roots; permissions stay scoped |
| Drive repeated analysis and human answers | Capture/restart does not dispatch an agent before explicit customer analyse; at least two question/answer rounds preserve history; waiting item does not block another; readiness stays unplayed |
| Persist dispatch and recover ambiguity | Crash-point fixtures exercise intent/start/response/commit; duplicate accepted response is a no-op; conflicting duplicate is rejected; uncertain started attempt is not blindly retried |
| Present minimal TUI and human commands | Rebuild view from Markdown; display malformed/failed/uncertain/waiting/ready states distinctly; validate analyse/answer commands; explicit play records scoped authorisation and shows delivery unavailable, with no delivery dispatch; verify using fake/guarded fixtures |

Suggested dependencies: contract before persistence/interpreter; those before
scheduler; dispatch context before real engine integration; fake adapters before
end-to-end analysis/TUI acceptance. First-slice tests should simulate roles and
crashes without launching the legacy runner or mutating external systems.
The PO's `type`, `state` and `authorisation` names are the canonical proposed basic
metadata. Architecture runtime fields extend that proposal; they do not establish
parallel kind/step/play state. Legacy import is part of planned slice acceptance.
`../qualities.md` records measurable correctness/integrity/control invariants and
proposed acceptance evidence; no performance or service-level target is invented.
STORY-009 makes play available as a decision-recording command while delivery
remains unavailable. A fake successor is verification machinery, not delivery.

## Assumptions (not customer decisions)

Kept here because this role owns only these three documents; delivery manager can
consolidate them into the shared assumptions register without duplicate authority.

| ID | Proposed assumption | What would change the answer |
| --- | --- | --- |
| A-ARCH-01 | One local trusted operator and coordinator per workspace; one active agent initially | Shared users, remote sessions or concurrent writers require explicit authentication and stronger coordination design |
| A-ARCH-02 | Local filesystem with atomic same-directory replacement and supported flush semantics | Network/synchronised folders or platform differences require measured guarantees and adjusted recovery |
| A-ARCH-03 | Manual edits use pause/edit/validate/resume | Requirement for unrestricted concurrent editor saves conflicts with the proposed protection; choose a stronger editing boundary |
| A-ARCH-04 | Constrained YAML is suitable for front matter | Existing parser/format constraints or round-trip requirements may change encoding/library choice |
| A-ARCH-05 | Product owner owns the illustrative analysis steps | Team/customer preference may assign another existing coordinating role without changing the mechanism |
| A-ARCH-06 | First slice can validate orchestration with fake adapters before enabling actual analysis dispatch | Need for immediate real-agent use adds permission, transcript and context tests |
| A-ARCH-07 | Local account identity suffices initially for customer commands | Multiple customers or regulated approval provenance requires an auth decision before play/release |

No throughput, latency, availability, budget, data classification, cloud provider
or new dependency has been agreed. No adoption research was performed. The GCP
line in the generic charter is not a constraint from this engagement's brief.

## Open decisions for coordinator collection

| ID | Owner to collect | Draft position and decision needed |
| --- | --- | --- |
| Q-ARCH-01 | Delivery manager/customer | Confirm local single-operator scope and expected item count; start with a proposed 100-item UI fixture, then agree a responsiveness target based on cost of delay |
| Q-ARCH-02 | Delivery manager/customer | Confirm pause/edit/resume is acceptable and identify supported OS/filesystem; do not promise unrestricted concurrent manual edits |
| Q-ARCH-03 | Product owner/quality lead | Agree required readiness fields and whether partial answers may be deliberately submitted; default proposal keeps incomplete requests waiting |
| Q-ARCH-04 | Platform engineer/customer | Classify brief/transcript data, retention and engine-provider access; product context may contain confidential material and needs explicit scope |
| Q-ARCH-05 | Delivery manager/product owner with architect | Legacy import is planned in slice one. Agree supported legacy stage/history/evidence mappings and representative fixtures; identify which ambiguous records need human resolution, preserve originals/provenance, and verify repeat/restart plus changed-source reconciliation |
| Q-ARCH-06 | Architect/platform engineer | Select front-matter parser after checking existing packaging and round-trip/error requirements; no library choice made here |
| Q-ARCH-07 | Product owner/quality lead with architect | Define scoped authorisation evidence and guarded/fake successor assertions for first-slice play verification; actual implementation remains deferred |

The brief confirms separate explicit play and release; the team proposes
explicit analyse before dispatch in the first slice. Q-ARCH-07 concerns
verification details, not reopening the planned fake/guarded play boundary.
Proposed quality evidence:
zero lost accepted transitions in crash fixtures; zero automatic retries of
uncertain side-effecting attempts; zero agent dispatches from capture alone;
zero real implementation dispatches throughout the first slice;
all adapter fixtures receive both charter and product brief. These are proposed
acceptance checks, not customer-approved service targets.

## Handoff

Delivery manager should consolidate these questions/assumptions and route the
first-slice boundary and editing protocol for customer review. Product owner
should incorporate the story proposals and preserve later epics for delivery,
testing/CI, GitHub, staging/UAT, release/rollback, sprint-zero generation and
specialist extensions. Quality lead should turn crash/conflict and gate examples
into backlog criteria; platform engineer should review filesystem/identity/data
assumptions. No other role's artifact was changed by the architect.
