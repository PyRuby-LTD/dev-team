---
schema_version: 1
id: STORY-004
type: story
title: "Validate workflows with one owner and named outcomes"
parent: EPIC-002
state: proposed
authorisation: not-played
depends_on: ["STORY-001"]
owner: product-owner
---

# Validate workflows with one owner and named outcomes

As the customer, I want each step to say who acts next so analysis has a clear accountable owner.

Define a versioned JSON workflow contract and ship a default workflow with the harness. Each step has exactly one agent or human owner and named outcome-to-target mappings. Bind agent names to repository-owned role definitions; agents may choose to consult other roles themselves. Do not define collaborators in the workflow.

## Workflow definition and work-item binding

The JSON contract includes workflow ID, version, initial state, states, owners,
named outcomes and targets, explicit guards, and terminal-state semantics. Each
state also supplies presentation metadata for STORY-007: group, label, order and
semantic style. Presentation metadata does not determine transition eligibility
or permissions. Validate the definition with a published schema, including
duplicate-key rejection rather than silently accepting overwritten JSON entries.

Each enrolled work item records a `workflow` object in its Markdown front matter
with `id`, `version` and `digest`, plus its existing `state` field identifying a
state in that definition. Resolve the reference through the bundled workflow
registry without machine-specific absolute paths. The digest pins the complete
definition, including presentation metadata. Do not duplicate runtime ownership
or add a second mutable step field to the work item. Choosing the default on
creation/enrolment must persist the explicit binding; reopening must never infer
the latest workflow or silently replace a missing reference.

The bundled default must prescribe the intended end-to-end delivery flow, not
just an illustrative analysis loop: capture, analysis and human clarification,
ready-to-play, explicit customer play, implementation, test writing, review,
automation testing, staging preparation, customer UAT, separate release approval,
release and completion. Specify a concrete sole owner and named transitions for
every state, including clarification, rework and UAT rejection paths. Human
clarification, play, UAT and release approval belong to the customer; agent-owned
states must resolve to explicit bundled roles, with any missing role definitions
identified for refinement rather than invented as already available.

Defining the full workflow does not implement all its stages. The first slice
still stops after recording play at the held delivery boundary. Document and
validate capability guards so unavailable delivery stages cannot dispatch or
fall back to the prototype pipeline. Defining later states grants no permission
to execute them. These planning stories remain unenrolled until the runtime
contract and registry exist; do not insert fictitious workflow digests now.

## Acceptance criteria

- [automated] Given the bundled default JSON workflow, when schema and semantic validation run, then its identity, initial state, every sole owner, named transition, guard, terminal rule and presentation mapping resolve unambiguously; malformed JSON, duplicate keys and invalid definitions produce actionable diagnostics. Evidence: default-workflow validation and negative fixtures.
- [automated] Given a work item created or explicitly enrolled with a selected workflow, when saved and reopened, then its front matter retains the workflow ID/version/digest and valid state without a second authoritative state or owner store; missing references, unknown states and digest mismatches prevent dispatch without silently choosing a default. Evidence: front-matter binding round-trip and refusal tests.
- [human] Given the default workflow and bundled role registry, when reviewed against the product delivery journey, then every stage from capture through release/completion has a concrete owner and named success, clarification or rework paths as applicable, and customer play and release approval are distinct gates. Evidence: reviewed workflow state/owner/transition table derived from the JSON.
- [automated] Given the full default workflow with only first-slice capabilities available, when analysis completes and the customer plays the current revision, then authorisation is recorded at the held delivery boundary and no unavailable implementation, test, deployment or release agent is dispatched. Evidence: capability-gate simulation with recording fake adapters.
- [automated] Given a valid captured/analysis/human/ready workflow, when validated, then captured belongs to human:customer with an explicit Analyse outcome before agent dispatch, each step resolves exactly one owner and every named transition resolves its target. Evidence: workflow validation fixtures using existing roles.
- [automated] Given missing or multiple owners, a collaborators field, unknown roles, unknown targets or duplicate/ambiguous outcome names, when validated, then execution is refused with specific diagnostics. Evidence: invalid-definition fixtures.
- [automated] Given an agent wishes to consult another role, when its response is evaluated, then consultation does not transfer ownership or bypass the named outcome contract. Evidence: owner/outcome contract test.
- [automated] Given a ready target, when workflow validation checks the path to delivery, then no analysis outcome can substitute for explicit customer play. Evidence: invalid bypass-path fixture.
- [automated] Given an item bound to a validated workflow version and content digest, when the definition changes in place or its pinned version is unavailable, then dispatch fails visibly without silently adopting the new definition. Evidence: pinned-version/digest fixtures.
- [automated] Given an explicitly selected workflow upgrade, when its step/request mapping is validated, then it preserves history and authorisation boundaries and records the new binding; unresolved active attempts or unmappable questions block migration. Evidence: version migration and refusal fixtures. Binding fields belong to the future runtime schema, not invented references in this planning record.
- [automated] Given a workflow completion outcome, when prerequisites are evaluated, then successful completion requires the validated front-matter completion record, current material-scope digest and evidence defined in architecture.md; no readiness, parent/child count or legacy status alone satisfies a dependency. Evidence: completion-contract fixtures consumed by STORY-009.

## Refinement and evidence

Source: [brief](../brief.md). Proposals and open questions: [scope](../scope.md). Reconcile with intended [architecture](../architecture.md), [qualities](../qualities.md) and [quality strategy](../quality-strategy.md) before play. These criteria specify future evidence, not completed tests. This is a proposed planning record, not an input compatible with the prototype runner.
