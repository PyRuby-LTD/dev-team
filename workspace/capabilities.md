# Capability map

Source: [brief](brief.md). Scope choices below are proposals pending customer prioritisation.

| Capability | User value | Planned coverage |
|---|---|---|
| Authoritative backlog | Capture and inspect durable epic/story/task/bug records without competing state, launched from the product directory with bundled team resources | EPIC-001; STORY-001–003, STORY-010 |
| Owned analysis and decisions | Know who acts next and repeat questions/answers until ready | EPIC-002; STORY-004–006 |
| Terminal visibility and control | See progress, answer questions and explicitly play selected ready work | EPIC-003; STORY-007–009 |
| GitHub and CI delivery | Follow implementation, tests, review and automation evidence | EPIC-004, deferred |
| Staging, user testing and release | Inspect a candidate and independently choose release | EPIC-005, deferred |
| Reusable products and sprint zero | Bootstrap a walking skeleton and introduce product specialists | EPIC-006, deferred |

Proposed first journey: capture an epic/story → request analysis → owning agent analyses → durable human question → customer answers → analysis repeats → ready, still not played → explicit customer play records authorisation at a visible hand-off boundary. First-slice play does not execute delivery.

Recovery journey: reopen the workspace → see current owner, outstanding request or execution uncertainty → reconcile the specific attempt → continue without replaying completed transitions or duplicating human requests.

Legacy journey: preview old records → resolve uncertain mappings → explicitly import → inspect preserved evidence and provenance. Original legacy files remain intact and are never consulted as competing live state.

Broader journey, deferred: explicitly played work → implementation → tests/review → automated checks → staging → customer user testing → separately authorised release.

Detailed acceptance evidence lives in each story and is refined with [quality strategy](quality-strategy.md). State and transition contracts are to be reconciled with [architecture](architecture.md) and [qualities](qualities.md).
