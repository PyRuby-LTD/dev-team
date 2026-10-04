# Quality invariants — proposed acceptance contract

Owner: architect. Status: proposed for refinement with the quality lead; no
implementation or acceptance tests have run for these proposals. Sources:
[brief](brief.md), customer corrections, [scope](scope.md),
[architecture](architecture.md) and [STORY-009](stories/STORY-009.md).
The numbers below are correctness assertions over specified fixtures, not
measured production guarantees or customer-approved service-level targets.

| Attribute | Measurable invariant and source | Proposed acceptance evidence |
| --- | --- | --- |
| Single authority | Exactly one live authoritative item record; its front matter owns state. Basic names are `type`, `state`, `authorisation` (brief and PO schema). | Rebuild views after deleting disposable caches; verify agreement with Markdown and no sibling JSON/DB state reads. Round-trip all four item types, hierarchy and narrative. |
| Validated ownership | Exactly one owner per step; zero accepted unknown outcomes, mismatched owners, stale responses or invalid workflow/schema versions (brief; architecture mechanics proposed). | Positive/negative contract fixtures, including changed workflow digest and missing role/target. Invalid items remain visible but ineligible. |
| Explicit analysis control | Zero agent starts from capture, refresh or restart before explicit customer `analyse` (team-proposed first-slice gate). | Fake adapter invocation count stays zero; accepted analyse creates one durable intent and routes to the owning analysis role. |
| Repeated human loop | At least two question/answer rounds preserve every submitted answer and request identity; one waiting item does not prevent another eligible item's progress (brief; two-round fixture proposed). | Scripted two-item trace, partial-answer persistence, restart and question-ID validation. Assert one durable request per dispatch rather than duplicate requests on reopen. |
| Managed-write integrity | Every crash fixture leaves one complete old or new item; zero accepted stale writes or lost acknowledged transitions under the supported editing protocol (proposed mechanics). | Inject failure around temporary write, flush, replacement and directory flush; compare revision/history. Detect body-only manual edits via full-file digest; test pause/edit/validate/resume. |
| Local idempotency and recovery | One accepted transition per consumed dispatch; zero extra transitions on identical response replay and zero blind retries of uncertain started attempts (proposed mechanics). | Crash before/after intent, start, response and commit; conflicting response-ID reuse fails; unresolved attempts remain visible for reconciliation. No exactly-once external-effect claim. |
| Explicit play boundary | Zero inferred play decisions from readiness, answers or elapsed time. One durable scoped decision per accepted play request; zero delivery dispatches in this proposed slice (brief and proposed STORY-009). | Fake/guarded fixtures assert current revision/content binding, prerequisites, stale/not-ready rejection, replay idempotency and the visible authorised/awaiting-delivery state. Assert no legacy runner, implementation agent or pending delivery attempt. |
| Permission scope | Zero child or release permissions inherited from parent play; zero eligibility for changed content using an old play decision (brief and STORY-009). | Parent/child fixtures, material-change invalidation and independent release-gate assertions. Record decision evidence in front matter. |
| Legacy preservation | Zero source-byte changes during preview or import; zero duplicate imported items/history on repeat/restart; zero inferred readiness/play/release from ambiguous legacy records (planned STORY-003). | Source checksums, preview filesystem comparison, ID collisions, unknown stages, changed-source reconciliation and verified history/evidence/provenance mappings. |
| Portable context | Every adapter fixture receives both selected role charter and product context plus permitted outcomes (proposed architecture). | Inspect fake invocation envelopes across engine bindings and relocated workspace roots; verify recorded context digests and scoped permissions. |
| Observable state | All fixture states distinguish business progress, operational failure/wait and permission; reopening reconstructs the same accepted decisions (brief and proposed TUI scope). | Mixed-validity view fixtures plus customer keyboard walkthrough showing questions, evidence, readiness and authorised work with delivery unavailable. |

Atomic rename does not prevent concurrent writes by an editor ignoring the pause
protocol. Filesystem guarantees must be verified on supported platforms; the
integrity assertion is conditional on that protocol and filesystem support.
Fake-adapter evidence does not establish live-engine compatibility. A separately
selected analysis pilot requires verified engine configuration and permissions.

Backlog volume, concurrency beyond the proposed local coordinator, latency,
throughput, availability, recovery-time/data-loss objectives, retention and cost
targets remain unconfirmed. Agree these from actual operating needs and failure
costs before defining a performance/SLO benchmark. Open decisions remain in
[architect analysis](analysis/architect.md); these invariants add no cloud,
dependency or deployment assumption.
