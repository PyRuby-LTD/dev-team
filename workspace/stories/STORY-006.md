---
schema_version: 1
id: STORY-006
type: story
title: "Recover safely from stale responses and uncertain attempts"
parent: EPIC-002
state: proposed
authorisation: not-played
depends_on: ["STORY-005"]
owner: product-owner
---

# Recover safely from stale responses and uncertain attempts

As the customer, I want interrupted work to resume visibly and safely so I do not have to guess whether an agent or answer was already processed.

Propose durable attempt/request identity and revision checks in Markdown. A resume operation must identify what is being reconciled; a blanket status reset is insufficient. Exactly-once external execution is not promised.

## Acceptance criteria

- [automated] Given a response for an older attempt, request, item revision or content digest, when received, then it cannot change current progress or replace a newer answer and its rejection is visible. Evidence: stale-response fixtures, including manual body edits.
- [automated] Given an accepted response, when it is delivered again before or after restart, then no second transition, history decision or next-owner dispatch is caused by that duplicate. Evidence: replay and restart trace.
- [automated] Given an accepted response identity, when a different payload reuses it, then it is rejected as a conflict rather than acknowledged as the earlier response or applied again. Evidence: conflicting-payload replay fixture.
- [automated] Given a crash around transition commit or next-owner dispatch, when the controller restarts, then known committed state is recovered and an uncertain dispatch is shown for reconciliation without blind rerun. Evidence: commit/dispatch fault matrix.
- [automated] Given an ambiguous running attempt, when resume lacks a matching attempt and reconciliation decision, then it is refused without new execution; a valid recorded decision permits only the corresponding recovery action. Evidence: ambiguity/recovery fixtures.
- [automated] Given a human request before restart, when recovery runs, then its identity and any accepted answer survive with no duplicate human request. Evidence: human-wait recovery fixture.
- [automated] Given launch failure, nonzero exit, cancellation or configured timeout, when an attempt ends, then failure remains distinct from progress and the UI remains responsive; cancellation terminates/reaps the owned process group or visibly reports unresolved descendants without trusting an old PID. Evidence: fake-process lifecycle tests; timeout duration is a policy still to select.
- [automated] Given a second coordinator or a changed harness build, when startup/restart is requested, then workspace ownership is validated and the process refuses conflicting operation; a build change occurs only after controlled shutdown and explicit restart. Evidence: lifecycle and competing-coordinator fixtures.
- [automated] Given a clean environment with declared dependencies installed but no provider credentials or engine CLI, when the documented fixture-only smoke runs outside the source tree, then packaged role/config resources resolve and the controller analysis loop and restart checks pass in a temporary workspace without external services. Evidence: install/smoke transcript and live-workspace non-mutation check. STORY-009 later adds guarded-play checks; this story does not depend on the future TUI. Real-engine checks require separate explicit selection.

## Refinement and evidence

Source: [brief](../brief.md). Proposals and open questions: [scope](../scope.md). Reconcile with intended [architecture](../architecture.md), [qualities](../qualities.md) and [quality strategy](../quality-strategy.md) before play. These criteria specify future evidence, not completed tests. This is a proposed planning record, not an input compatible with the prototype runner.
