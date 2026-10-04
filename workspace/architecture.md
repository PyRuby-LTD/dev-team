# Harness architecture — analysis proposal

Status: proposed for team/customer review; analysis complete; unplayed. Source:
`brief.md`. Technical mechanics below are proposals, not confirmed defaults.

## Confirmed boundaries

Python controls named, validated workflow outcomes. Work-item Markdown front
matter is the sole authoritative item state, including questions, answers,
decisions, execution metadata and history. Each step has exactly one agent or
human owner; an agent may choose to consult another role. Analysis may repeatedly
return to the human. Readiness, customer play and customer release are separate.
GitHub matters for later integration. No local database is required or proposed.
This engagement authorises analysis and backlog creation only.
The team proposes an explicit `analyse` action on newly captured backlog before
any agent starts or spends tokens; capture alone is not dispatch in this proposed
first slice. This is not a new customer instruction received during analysis.

## Proposed smallest system

One local Python coordinator per engagement workspace owns scheduling and item
writes. A process lock prevents two coordinators; it is coordination metadata,
not item state. A Markdown repository layer validates and replaces item files;
a workflow interpreter checks outcomes; an engine adapter dispatches role briefs;
a terminal UI reads items and submits human commands through the coordinator.
An in-memory index is disposable and rebuilt from Markdown. No distributed
service, broker or durable secondary queue is needed.

The scheduler scans eligible items fairly. Waiting human requests are persistent
item data, not a blocking terminal read. Proposed initial agent concurrency is
one; other items remain eligible while an item waits on a person or requires
recovery. Engine execution must not block the UI/coordinator event loop.

## Proposed front-matter contract

Use a constrained YAML mapping between Markdown delimiters. Parser/library choice
is unresolved; no dependency adoption is implied. Reject duplicate keys, custom
tags, invalid types, unknown schema versions and inconsistent references. Keep
the body for narrative and acceptance criteria. State asserted in prose does not
override front matter. Basic metadata follows the PO's proposed planning contract
in `scope.md` and STORY-001. This example is not input to the prototype:

```yaml
---
schema_version: 1
id: STORY-EXAMPLE
type: story
title: Analyse a captured feature
parent: EPIC-EXAMPLE
state: proposed
authorisation: not-played
depends_on: []
---
```

Runtime fields are an extended schema proposal, not requirements already met by
the planning records: `product`, `revision`, pinned `workflow` (ID/version/digest),
`execution` (status/dispatch/error), `questions`, `decisions` and `history`.
`state` remains the single business-state field, mapped to the pinned workflow's
step; do not add a competing `step` field. The demonstration's captured step maps
to planning `state: proposed`; other runtime state values need schema validation.
`authorisation` remains the permission field; do not add a competing `play` field.
Scoped play and separate release decision evidence belongs in `decisions` and
`history`; allowed authorisation values and guards are extended-schema design.
Planning records have no invented workflow binding and are not schedulable until
explicitly enrolled in a validated runtime workflow. Pending customer priority
is a planning condition, not an additional competing state field.

Required identity fields are stable; types are epic/story/task/bug; parent is null
or a valid same-product item ID. Reject duplicate IDs, missing parents and cycles.
Parent completion does not automatically follow child state in the first slice.
`revision` increments on every accepted mutation. The workflow-mapped `state` is business
progress; execution status (idle/pending/running/waiting-human/failed/uncertain)
is operational state and must not masquerade as progress. Owner is derived from
the pinned workflow, never duplicated as independently mutable item state.

Questions carry stable IDs, text, raised-by identity/time, and append-only answer
entries with actor/time/text. Decisions carry IDs, rationale, provenance and
proposed/accepted/rejected status. History entries carry unique event ID, actor,
timestamp, before/after revision and step, named outcome, response/dispatch ID,
and relevant evidence references. Accepted responses and their payload digest
are retained in history so deduplication survives restart. Evidence and logs may
be linked, but deleting a log must not erase whether a transition occurred.

An active dispatch contains its stable ID, expected item revision and complete
file digest, workflow identity, owner, input-context digests, intent timestamp,
attempt records and accepted response identity when available. Human requests
use this same durable identity/correlation mechanism. Authorisation records bind
customer identity/time and scope to the analysed item revision/content; later
material changes require renewed authorisation. Do not infer approval from prose.

## Workflow and response boundary

### Proposed dependency semantics

`depends_on` lists direct prerequisites for play/delivery, not prerequisites for
capture, analysis or answering questions. Parent hierarchy does not inherit
dependencies or authorisation. Epic dependencies express ordering of the epic's
own scope; any prerequisite that must constrain a child is explicitly listed on
that child. The planning sequence in plan.md uses the same direct references.

A prerequisite is satisfied only when its front matter records a validated
`completion` with `outcome: verified`, nonempty evidence references and a
`scope_digest` matching its current material scope, and its pinned workflow
identifies the current state as successful completion. The completion record is
written through the validated verification/human-acceptance outcome, not inferred
from prose, `ready`, an exited process, child counts or legacy `done`. Missing,
unknown, stale or unverified prerequisites block play with an explanation.
An epic requires its own accepted outcome; child completion alone does not supply
one. Cancelled/deferred work does not satisfy prerequisites.

This is a proposed runtime contract to refine in STORY-004 and verify in
STORY-009, not an assertion that these proposed backlog records are complete.
Until the contract is implemented, the gate refuses unresolved prerequisites.
Use both satisfied and unsatisfied fixture records in the first-slice play test;
real implementation remains held at the delivery boundary.

Proposed workflow definitions contain ID/version, initial step, and steps with
exactly one `owner` consisting of kind (agent/human) and role, plus a mapping of
allowed outcome names to target steps and explicit guards. Engine/model choice
and tool permissions belong to role/adaptor policy, not workflow ownership.
Validate owners against the role registry, targets against steps, and reachability
and terminal/gate rules before dispatch. Consultation is chosen by the owning
agent; its result remains that owner's responsibility and grants no extra tools
or transition authority.

An agent or human response envelope contains `response_id`, `item_id`,
`dispatch_id`, `expected_revision`, `expected_file_digest`, workflow ID/version/
digest, authenticated submitting actor, `outcome`, and typed `payload` (questions,
answers, proposed decisions, narrative/evidence changes). Actor identity comes
from the invocation or local human session, not a trusted self-assertion inside
model text. Responses cannot select arbitrary target steps or patch protected
state. Python validates correlation, current owner, outcome, payload and guards,
then computes the target and commits. Invalid JSON/schema, missing responses,
unknown outcomes and nonzero engine exits are failures with evidence, not
successful workflow outcomes. Human answers must address the current question
IDs; partial answers stay at the human step until deliberately submitted under
the agreed completeness rule.

### Demonstrative flow (Markdown design only)

| Step | Sole owner | Named outcome → next step |
| --- | --- | --- |
| captured | human: customer | analyse → analysis |
| analysis | agent: product-owner | needs-answer → human-answer; analysis-ready → ready-to-play |
| human-answer | human: customer | answers-submitted → analysis |
| ready-to-play | human: customer | stop: readiness recorded, item remains unplayed |

Capture and scheduler restart leave the item waiting for the customer's explicit
`analyse` action; neither creates an agent attempt. The product owner shapes the
first slice once analysis is requested. `needs-answer` requires nonempty identified
questions; `analysis-ready` requires
resolved blocking questions and reviewable acceptance criteria. Repeating the
human loop creates new request IDs and preserves previous answers. This discovery
example ends at ready-to-play. STORY-009 additionally provides an explicit `play`
command: validate readiness, prerequisites and the current revision/content digest,
then persist one scoped customer authorisation decision and show authorised work
awaiting delivery capability. Repeated requests are idempotent; material changes
invalidate the old permission for the changed content. Parent play does not
authorise children. Play is available, but delivery capability remains unavailable:
the command creates no implementation dispatch or pending delivery attempt.
A fake/guarded successor verifies this boundary in acceptance fixtures only; it
is not an operational delivery target. Never fall back to the old runner.
Release is a separate future customer
gate after staging/UAT, never an implication of play or an analysis answer.

## Atomic changes, manual edits and recovery

Proposed managed writes acquire the coordinator's mutation lock, reread the whole
file and compare both expected revision and a SHA-256 digest of the original
bytes. The digest detects body edits and manual edits which forgot to increment
revision. Validate the complete candidate, write a temporary file in the same
directory, flush/fsync it, atomically replace the item and fsync the directory on
supported local filesystems. Commit state, accepted response ID, history and next
dispatch intent, when the target is eligible for dispatch, in that one replacement.
Captured, ready-to-play and authorised-awaiting-delivery items create no agent
intent. Readers see either complete version.
ID allocation and hierarchy validation also occur under the workspace mutation
lock; no multi-item atomic transaction is promised.

Atomic rename is not compare-and-swap against an uncooperative text editor. The
proposed supported manual-edit protocol is to pause coordinator writes for that
item, edit, then resume through validation and a recorded import/revision bump.
Before resuming, invalidate any outstanding response whose source bytes changed.
Edits detected outside that protocol cause conflict handling, not silent merging;
a final digest check narrows but cannot eliminate an uncooperative concurrent
write race. This limitation must be documented and tested, not described as
universal lost-update protection. Malformed files remain visible as errors and
are not overwritten. Paused state and imported-change provenance belong in front
matter; ephemeral locks are not an alternative authority.

Persist dispatch intent before invoking any process or exposing a human request.
Before actual invocation, persist its attempt start under the same dispatch ID.
On response, an already accepted response ID with the same payload is a no-op;
the same ID with a different payload is rejected. Only one response can consume
a dispatch. Stale or competing responses never advance a newer revision.
Preparing the next intent in the transition commit closes the gap between
advancing an item and remembering to dispatch its next owner.

Restart rebuilds pending work from front matter. An intent with no started
attempt can be dispatched. A started attempt without a committed response is
uncertain: the process may have run even if the local acknowledgement was lost.
Reconcile available evidence or ask the human before retrying; record the choice
and a new attempt. A later approved adapter may retry safely using a provider's
idempotency key or query API. Neither a local intent nor atomic file replacement
guarantees exactly-once external effects. External mutations remain outside the
first slice. Accepted transitions are locally idempotent; dispatch itself may
require reconciliation. Test crashes before/after intent, invocation and commit.

## Versioning and portable dispatch

Pin each item to an immutable workflow ID/version/content digest. Editing a
definition in place must fail digest validation. Existing items keep their
version; upgrades require explicit validated migration mapping old steps and
outstanding questions/dispatches, with history recorded per item. Do not migrate
an active dispatch until resolved or explicitly cancelled. Schema versions are
separate from workflow versions; unsupported versions fail visibly.

The prototype selects this analysis through `config/workspace` (`./workspace`).
For the final product, [STORY-010](stories/STORY-010.md) requires the invocation
directory to select the product and the harness checkout/package to supply all
bundled resources, independently of user-installed skills or agents. Package
reusable role identity/charter separately from product context. Each dispatch
receives the selected `team/` charter, item snapshot,
workflow/outcomes, product brief and confirmed constraints, scoped repository and
workspace roots, evidence references, and permission policy. Record context
versions/digests and retain reviewable snapshots as non-authoritative evidence.
Resolve portable product-relative references at dispatch, not embedded
machine-specific absolute paths in every work item. Product-specific specialist
roles may extend an explicit registry without replacing the reusable core roles.

Current `Role.brief()` reads `roles/`, whereas engagement charters are in `team/`;
an explicit registry mapping must resolve this distinction. Engine adapters must
actually deliver both role brief and product context: the current Claude command
uses `{brief}`, while the current Codex command does not. No adapter may silently
omit these inputs. Do not copy the architect charter's incidental GCP sentence
into product constraints: the authoritative brief specifies no cloud provider.

## Prototype evidence and backlog implications

| Current source | Architectural gap |
| --- | --- |
| `devteam/workitem.py` | `state.json` authority; direct non-atomic writes; no revision conflict protocol; directory-count ID allocation |
| `devteam/pipeline.py` | Hard-coded stages/outcomes; investigation enters implementation; worktrees and write-capable execution; no durable dispatch identity |
| `devteam/cli.py` | Direct state mutation in human decisions; resume/approve lack scoped outcome validation; no TUI |
| `devteam/engines.py` | Blocking subprocess; transcript plus exit code; no correlated typed response or ambiguous-attempt recovery |
| `devteam/config.py`, `config/roles.toml` | Useful workspace and engine separation; legacy role paths and uneven brief delivery |
| `devteam/__main__.py`, `devteam/__init__.py` | Thin entry point/empty package; no additional orchestration guarantees |

Reuse workspace resolution and the adapter concept after review. The new schema
is incompatible with the prototype; discovery records must not be passed to its
runner. Legacy import is in the planned first slice (STORY-003 and `plan.md`):
preview mappings without writes, explicitly apply reviewed mappings, and retain
original files byte-for-byte as historical evidence, never competing live state.
Preserve identity, provenance, meaningful history and evidence links. Unknown
stages, ID collisions and unclear legacy approvals need resolution; do not infer
readiness, play or release. Repeated/restarted import must not duplicate items or
history; changed sources require reconciliation. Exact stage/evidence mappings
remain an open design question, not whether to include import.
Story proposals and verification boundaries are in `analysis/architect.md` for
the product owner/delivery manager to incorporate into their backlog.

Later named epics remain: implementation and review orchestration; automated
testing and CI; GitHub integration; staging and customer UAT; customer-controlled
release and rollback; sprint-zero walking-skeleton/infrastructure generation;
product specialist extensions. They need further analysis before execution.
