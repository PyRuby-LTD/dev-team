# Scope

Authority: [brief](brief.md), in particular its final section.

## The first slice: EPIC-001

A work item has a workflow. The workflow is JSON and names the owner of each
step and its valid transitions. The item's front matter holds its current step.
Python reads the step: for an agent-owned step it invokes the role, engine and
model from `config/roles.toml`; for a human-owned step it waits. A terminal UI
shows every item and its step, and lets the customer answer questions and move
an item along one of the transitions its step allows.

Work begins with a request, which is itself a work item with its own workflow.
The product owner analyses it, asks the customer questions, passes it to other
roles for input and decides when analysis is complete; the output is epics,
stories, tasks and bugs.

| Story | Result |
|---|---|
| [STORY-001](stories/STORY-001.md) | Workflow JSON, loader, and step transitions on a work item |
| [STORY-002](stories/STORY-002.md) | Runner that invokes the owning agent and applies its transition |
| [STORY-003](stories/STORY-003.md) | Terminal UI listing items by step and owner |
| [STORY-004](stories/STORY-004.md) | Answering questions and choosing transitions in the UI |
| [STORY-007](stories/STORY-007.md) | Work visibly in the checkout on a branch per item; backlog on its own branch; pull request on accept |
| [STORY-005](stories/STORY-005.md) | Enter a request, have the roles analyse it, and get work items created from it |

## Next: EPIC-002

[STORY-006](stories/STORY-006.md): launch from any product directory using the
team definitions in the dev-team checkout.

## Later, no stories yet

- [EPIC-003](epics/EPIC-003.md): GitHub and CI delivery; test-writing and
  automation-test steps.
- [EPIC-004](epics/EPIC-004.md): staging, user testing and a separate release
  decision.
- [EPIC-005](epics/EPIC-005.md): sprint zero for a new product, and product
  specialists.

## Deliberately left out

- Any front-matter state beyond `step`: no authorisation flag, execution status,
  revision, digest or history. Play is a transition out of a human-owned step.
- `depends_on`. The customer chooses what to play and in what order.
- Workflow version pinning and migration, guards and display metadata.
- Crash reconciliation, replay protection and concurrent-writer protocols.
- Import of legacy `ITEM-NNN` directories.

Add any of these back when a real failure or need shows up, as its own story.
