---
id: EPIC-001
type: epic
title: "Workflow-driven work items"
---

# Workflow-driven work items

The happy path. It starts with a request: the customer enters an idea, feature or
change, the product owner and the roles it calls on question them, and the
result becomes epics, stories, tasks and bugs. From there, a
work item has a workflow; the workflow is JSON naming the
owner of each step and its valid transitions; the item's front matter holds its
current step. Python reads the step to decide whether a human or an agent acts
next, invokes the configured agent and model for agent-owned steps, and a
terminal UI lets the customer see every item's step and act on the human-owned
ones.

Stories, in build order: [STORY-001](../stories/STORY-001.md),
[STORY-002](../stories/STORY-002.md), [STORY-003](../stories/STORY-003.md),
[STORY-004](../stories/STORY-004.md),
[STORY-005](../stories/STORY-005.md). [STORY-007](../stories/STORY-007.md) was added
later and should be built straight after STORY-002.

## Done when

- The customer can enter a request, answer the team's questions and receive
  drafted work items.
- The customer can capture a story, send it for analysis, answer the analyst's
  questions, see it reach `ready`, and play it, entirely from the terminal UI.
- Changing an owner or a transition means editing the workflow JSON, not Python.

Source: [brief](../brief.md).
