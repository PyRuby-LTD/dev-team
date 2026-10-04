# Assumptions and proposed defaults

Owner: delivery manager maintains the register; technical/content owners are named.
Status date: 2026-10-02. Confirmed facts are in [brief.md](brief.md).

| ID | Proposal / inference | Owner | Status | What changes the proposal |
|---|---|---|---|---|
| A1 | First pilot uses one local customer and one coordinator per product. | architect | proposed | Concurrent operators or controllers on different machines require shared coordination. |
| A2 | Keep the configured `./workspace` as the current analysis output location. | delivery manager | existing configuration, not a long-term storage decision | Customer chooses a product repository/branch policy (Q1). |
| A3 | First implementation slice ends at an explicit play boundary and includes a minimal TUI. Full delivery/release are later epics. | product owner | proposed scope | Customer reprioritises GitHub execution or another end-to-end slice. |
| A4 | Human answers are saved before an explicit submit action resumes analysis. | product owner | proposed | Customer prefers automatic submission after all required answers (Q4). |
| A5 | Deterministic fake agents exercise the controller before a live engine pilot. | quality lead | proposed validation approach | A real engine remains necessary to validate the configured adapter, but not each transition test. |
| A6 | Work-item metadata may reference external large artifacts without duplicating state there. | architect | accepted design interpretation | Customer requires embedding all evidence/transcripts in each Markdown document. |
| A7 | No cloud deployment of the harness is required for the first local pilot. | platform engineer | proposed | Customer needs an always-on remote service immediately. Target-product deployment requirements remain separate. |
| A8 | Managed mutations use atomic file replacement and revision plus full-content checks; manual editing follows pause/edit/validate/resume. | architect | proposed | Unrestricted concurrent editing or a synchronised/network filesystem requires a stronger coordination design. |
| A9 | Play in the first slice records a scoped decision at a held delivery boundary; it cannot launch the old implementation pipeline. | product owner | proposed | Customer requires actual implementation in the first slice, expanding EPIC-004 into it. |
| A10 | Runtime role selection explicitly maps to the existing team charters and configured engines; sample engine names/models are not proof of availability. | architect / platform engineer | proposed | The verified local provider profile or role mapping differs. |
| A11 | Newly captured backlog waits for explicit Analyse before spending agent time. | product owner | proposed first-slice control | Customer prefers automatic analysis on capture; explicit implementation play remains unchanged. |
| A12 | Direct prerequisites gate play/delivery and require verified completion with current scope-bound evidence; hierarchy neither inherits dependencies nor grants permission. | architect / product owner | proposed runtime semantics | Customer needs another dependency policy or explicit inherited prerequisites. |

## Consolidation of role proposals

Product-owner proposals PO-A1 through PO-A7 in scope.md map to A1, A9, the
confirmed work-item types, STORY-003, the TUI request surface, scoped-authorisation
invalidation in STORY-009, and recovery in STORY-006 respectively. Architect
assumptions A-ARCH-01 through A-ARCH-07 map to A1/A8/A10 and unresolved parser,
readiness and local-identity choices. Platform assumptions PA1 through PA5 map to
A1/A5/A7 and the proposed stable-runtime and evidence policies in platform.md.
These reports explain alternatives; they are not additional authoritative backlog
records. None of these technical proposals is promoted to a customer decision.

## Explicitly not assumed

- No GCP commitment: the architect charter's product-specific GCP sentence is not
  a requirement for this harness or future products.
- No Linear account, local database, dedicated metadata branch or remote issue
  creation has been chosen.
- No provider subscription entitlement, cost, available model or CLI compatibility
  is inferred from the sample engine configuration.
- There is no customer deadline, scale target or monthly budget to quote.
- Permission to analyse/create work is not permission to play it.
- Agent roles and explanatory examples do not dictate workflow collaborator lists.

Role reports under `analysis/` identify additional technical proposals. They are
not approved customer requirements merely because they appear in this workspace.
