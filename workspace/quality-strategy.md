# Quality strategy

Owner: quality lead. Status: proposed verification plan, 2026-10-02.

This is analysis for the harness described in [brief.md](brief.md), not evidence
that the proposed controller exists. All resulting backlog remains unplayed and
pending customer prioritisation. No implementation, test scripts, live agent
runs, publication or deployment are authorised by this document.

## Evidence contract

Each story should name its applicable checks below, label criteria `automated`
or `human`, and specify the evidence retained. Automated evidence means an
asserted result from a reproducible check, not an agent saying checks passed.
Human evidence means a named review decision against a specific artifact or
scenario, including findings; screenshots alone do not prove usability.

Use deterministic fake adapters first, temporary local workspaces, controllable
responses and interruption points. Retain initial/final Markdown, validation
results, dispatch calls, relevant event order and failure/recovery observations.
Logs and test reports are evidence, never alternative authoritative item state.
Do not log credentials or unnecessary customer content in evidence bundles.
No tests or live pilot have been run as part of this analysis.

## Focused acceptance checks

| ID / level | Checkable acceptance criterion | Evidence |
|---|---|---|
| V0 — automated, analysis intent | Capture/import, scans, refresh and restart leave a new item undispatched until an explicit customer analyse intent is durably accepted. Validate that command against the current item/revision, record it once, and make only analysis eligible. Replayed or stale analyse commands cannot launch duplicate work. Analysis intent grants neither play nor release. | Zero-call capture/restart traces; command validation and replay fixtures; recorded intent. |
| V1 — automated, parser/storage | Load epic/story/task/bug records using the agreed schema. Identity, hierarchy, workflow state, questions, answers, decisions, execution metadata and history come from Markdown front matter. Rebuild views after deleting disposable caches; conflicting legacy JSON cannot override Markdown. Reject malformed YAML, duplicate keys/IDs, invalid types, broken relationships and unsupported schema versions with actionable diagnostics and no dispatch. Preserve narrative and agreed extension metadata on round-trip. | Fixture matrix, reload assertions, before/after documents and diagnostics. |
| V2 — automated, workflow contract | Validate exactly one agent or human owner per step, resolvable owners, declared outcomes and existing targets. Reject missing/multiple owners and collaborator declarations. Reject a response with the wrong item, owner, step, workflow version, run identity or expected revision, or undeclared outcome; no state transition or next dispatch occurs. A valid response commits the mapped transition before dispatching its next owner. | Valid/invalid definitions and response matrix; ordered persistence/dispatch trace. |
| V3 — automated, controller integration | Exercise capture → analysis → durable human questions → answer → analysis, including a second question round and multiple questions. Persist stable question/answer relationships, partial answers and answer revisions. Reload during human waiting and recover the same request. Under proposed explicit submission, saving a partial or complete draft alone does not resume; valid submit resumes once and supplies the persisted answers. Reject answers for closed/superseded requests. | Markdown snapshots across restarts; fake agent input; dispatch counts and rejection results. |
| V4 — automated, authority boundary | Analysis completion records readiness while permission remains unplayed. Saving answers, submitting answers, scheduler ticks, reconnects and restarts never grant play. Reject play from an unauthorised actor, wrong state or stale revision. An explicit authorised play command is scoped to the selected item/revision and is idempotent. For the proposed first slice it records the boundary only; implementation and release adapters receive no calls. | Authority matrix; durable decision and zero implementation/release calls across all scenarios. |
| V5 — automated, response handling | Deliver one valid response twice, then an older response after a newer run, a response after a manual edit, and a conflicting payload reusing an identity. At most one transition/history acceptance and next dispatch occur for the accepted response. Duplicates have an explicit no-op result; stale/conflicting responses are rejected with reason and cannot overwrite current content. | Response identities, snapshots, acceptance history and fake dispatch counts. |
| V6 — automated, restart/fault integration | Interrupt before transition commit, after commit before dispatch, after durable dispatch intent before launch, after launch before acknowledgement, after response arrival before commit and after commit before acknowledgement. Recovery either safely completes known pending work or exposes an uncertain run for reconciliation. Never blindly relaunch a possibly started non-idempotent run or claim exactly-once external execution. Agent failure, invalid output and uncertain execution remain distinguishable from workflow progress. | Failure-point matrix, durable execution records, restart traces and fake invocation counts; explicit unresolved-run result. |
| V7 — automated, filesystem integration | A transition updates state, history, question/answer changes and execution metadata as one document commit. Inject write/replace errors and interruption around the declared persistence boundary: readers see the old or new valid document, never truncated content. Race two controller writes and controller/manual saves, including body-only edits and same-size edits. A stale controller write preserves the manual change and surfaces a conflict; no silent last-writer-wins overwrite. An invalid manually edited file is diagnosed and not dispatched. | Before/after bytes, conflict results and filesystem fault traces on supported filesystems. See manual-edit limitation below. |
| V8 — automated, scheduler integration | While item A waits for a human, eligible item B advances without answering A. An invalid, failed or uncertain item does not terminate scheduling for unrelated valid items. Repeated scans do not redispatch waiting/running work. Demonstrate ordering with controllable fake agents, including a pending agent call if asynchronous scheduling is promised. | Event order and dispatch ledger; no wall-clock speed claim or invented throughput target. |
| V9 — automated, TUI integration | Disconnect/reconnect the TUI while waiting, answering and transitioning. Rebuild its view from committed records, show current owner, readiness, play permission, questions, failures and uncertain execution, and reject stale actions. A submitted answer/play request whose acknowledgement was lost is not applied twice. Closing the TUI does not resolve a request or grant permission. | Headless interaction transcript, persisted records and replayed action results. |
| V10 — human, local walkthrough | The customer can locate an item, identify its owner and next action, answer questions, distinguish saved versus submitted answers and ready versus played, and understand a conflict or uncertain run after reconnect. Show later delivery stages as deferred capability rather than implying they are operational. | Recorded customer decision and findings tied to the demonstrated build and scenario. |

These are behavioral requirements and proposed test cases; exact field names,
command names and states follow the agreed architecture. Readiness to analyse is
distinct from permission to implement. Invalid input may produce a diagnostic
but must not be treated as a successful workflow transition.

## Atomicity and manual-edit boundary

Atomic replacement prevents a partially written destination; it does not alone
prevent lost updates. A revision field alone cannot detect an editor changing
only the body without incrementing that field. Propose comparing the full file
content against the loaded version and defining a coordinated write protocol.
A noncooperating editor can still save between a comparison and replacement.
The architect must specify the supported editing protocol and recovery behavior,
including lock participation or a requirement to pause the controller for edits.
Do not accept a universal no-lost-updates claim based only on rename plus hash.
V7 must exercise the exact supported protocol and demonstrate handling of edits
outside it; any unavoidable limitation must be visible in customer guidance.
Process-crash tests do not establish power-loss durability: the platform owner
must define the supported filesystem and durability scope before that claim.

## First-slice end-to-end evidence

Using fake adapters, capture two items and demonstrate zero dispatch until each
receives explicit analyse intent. Have A ask questions twice, persist a
partial answer, restart and reconnect, submit the remaining answers, and reach
ready-to-play with permission still unplayed. While A waits, advance B. Inject
a duplicate response and stale answer, then a conflicting manual edit and a
dispatch interruption. Demonstrate rejection/conflict/uncertainty without lost
answers, unauthorised play or duplicate accepted transitions. Recover only as
the agreed contract permits. Inspect both documents and the rebuilt TUI.
Test an explicit play request on an isolated fixture using a fake/guarded
successor only, without implementing the item; it must not play any of this
engagement's actual backlog. Recording authorisation and demonstrating a guarded
handoff do not establish real delivery capability.

## Proposed gates and infrastructure backlog

Final review additions: STORY-005 must supply automated adapter-contract evidence
that the selected role charter and product context actually reach each adapter,
and isolated denial evidence for protected metadata/code writes and path escapes.
Fake permission checks cannot establish live engine isolation. STORY-006 adds
automated lifecycle evidence for launch failure, cancellation/timeout, owned
process cleanup, competing coordinators, controlled build restart and installed
resource resolution outside the source tree. Use configured policies, not invented
timeout or performance values. These supplement V2/V6/V8 and remain future checks.
STORY-009 records play with delivery held: only a fake/guarded successor may be
used for verification, with zero legacy implementation or release invocation.

Before dependent implementation is selected, product owner and architect should
resolve the policy questions in [the role report](analysis/quality-lead.md), map
each story to applicable V checks, and preserve unplayed planning metadata.
Proposed infrastructure tasks for their backlog: a deterministic fake adapter
and call recorder; schema/workflow fixtures; a controllable scheduler; storage
fault and restart hooks; isolated filesystem fixtures; headless TUI interaction
and reconnect support. These are proposals, not scripts delivered here.

Before first local pilot, require applicable V0–V9 results against the selected
build and supported environment, and a reviewed disposition for failures.
Unresolved authority, data-loss, duplicate dispatch or unknown-run retry defects
block the pilot. V10 supplies the human usability gate. Passing these checks
does not authorise release; future CI, staging and deployment stories must add
their own checks and separately controlled release decision.

A limited live analysis pilot is separate and requires explicit analysis
authorisation for its input item plus a verified adapter profile. That input
remains unplayed: analysis authorisation is not implementation permission.
Implementing the pilot capability itself requires separate customer selection
and play of its implementation story; those decisions do not authorise analysis
of arbitrary input items. Platform engineer checks
the installed engine, authentication, permissions and configured model without
assuming the sample configuration works. Use a disposable local product with
an agreed scope and stop conditions; inspect role invocation, real output
validation, durable questions and restart behavior. Automated adapter evidence
proves protocol handling; human review judges whether analysis and questions
are useful. A live run cannot substitute for deterministic race/fault coverage.
No live run or external write is part of this commission.

## Deliberate exclusions

Multi-host concurrency, full delivery execution, GitHub/CI integration, staging,
release, sprint-zero generation and specialist roles belong to later epics.
Their deferral does not waive first-slice authority or persistence checks.
Do not test provider quality on every transition, or claim fake adapters prove
live CLI compatibility. No load benchmark, latency SLA, capacity, cost ceiling
or deadline is asserted: none was supplied. Q5 in engagement.md owns discovery
of those constraints. Measure against agreed targets only when they exist.
