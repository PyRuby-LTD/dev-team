---
schema_version: 1
id: STORY-005
type: story
title: "Progress analysis through durable human questions"
parent: EPIC-002
state: proposed
authorisation: not-played
depends_on: ["STORY-002","STORY-004"]
owner: product-owner
---

# Progress analysis through durable human questions

As the customer, I want to answer analysis questions over several rounds so ready work reflects my decisions.

The Python controller selects explicitly analysis-authorised work, dispatches its owning agent and validates responses against the current attempt/revision/content digest and named outcome map before committing. For human-owned steps it exposes a durable request in front matter. Human waiting must not block unrelated eligible work. Apply [platform permission separation](../platform.md): only the controller writes authoritative metadata; analysis agents submit results through a scoped channel and cannot edit target code or play/release decisions.

## Acceptance criteria

- [automated] Given analysis needs two rounds of clarification, when the matching human answers arrive, then both question/answer rounds and decisions persist and analysis resumes until ready, still unplayed. Evidence: agent-double end-to-end trace and final front matter.
- [automated] Given an agent proposes an unknown outcome, arbitrary target or malformed response, when Python validates it, then it records a distinct failure without advancing the workflow. Evidence: response contract fixtures.
- [automated] Given a response for the wrong item, owning role, dispatch or workflow version/digest, when it is received, then trusted invocation identity and correlation checks reject it without changing the item or scheduling its next owner. Evidence: mismatched-envelope fixtures.
- [automated] Given one item waiting for a human and another eligible for analysis, when the scheduler iterates, then the second can progress and the first retains the same durable request. Evidence: multi-item scheduler trace.
- [automated] Given a committed human request, when the scheduler ticks repeatedly, then it exposes the same request identity without creating duplicate requests or dispatching the waiting owner again. Evidence: repeat-tick fixture.
- [automated] Given an analysis engine or consultation attempts a protected write, path escape or unauthorised external capability, when its permissions are checked, then the operation is denied; an adapter unable to enforce the required boundary is not dispatched. Evidence: isolated permission-denial and path/symlink fixtures; fake-engine tests do not establish live-engine isolation.
- [automated] Given an eligible analysis attempt, when dispatch is prepared, then its selected team charter, product brief/context, workflow revision, harness build and engine configuration identifiers are supplied and recorded without raw credentials or transcripts in routine logs. Evidence: adapter context contract and redaction fixtures.
- [automated] Given each supported engine adapter and identical selected role/product inputs, when an isolated invocation is prepared, then each adapter receives the same charter, brief, confirmed constraints and outcome contract without silently omitting context. Evidence: per-adapter invocation contract fixtures.
- [automated] Given a selected live analysis engine, when its executable, result channel and enforced analysis-only permissions cannot be verified, then the live pilot is refused before dispatch; missing executable, launch failure, nonzero exit, timeout and cancellation remain separate visible failure categories rather than named success outcomes. Evidence: preflight refusal and lifecycle-category fixtures, plus separately selected real-engine boundary evidence before any live pilot.

## Refinement and evidence

Source: [brief](../brief.md). Proposals and open questions: [scope](../scope.md). Reconcile with intended [architecture](../architecture.md), [qualities](../qualities.md) and [quality strategy](../quality-strategy.md) before play. These criteria specify future evidence, not completed tests. This is a proposed planning record, not an input compatible with the prototype runner.
