---
id: STORY-004
type: story
title: "Act on human-owned steps in the terminal UI"
parent: EPIC-001
workflow: default
step: implement
---

# Act on human-owned steps in the terminal UI

As the customer, I want to answer questions and move an item to its next step
from the terminal UI, so I control analysis, play and acceptance without
editing files.

## Notes

For an item at a human-owned step, offer exactly the transitions that step
defines in the workflow JSON; choosing one moves the item (STORY-001). When the
body has unanswered questions under `## Questions`, let the customer type
answers, which are written into the body beneath each question before the
transition is applied. Run the STORY-002 loop alongside the UI so that an item
moved to an agent-owned step is picked up without leaving it.

There is no separate "play" mechanism: play is the `play` transition out of
`ready`, which is human-owned.

## Acceptance criteria

- Given an item at a human-owned step, then the actions offered are exactly that
  step's transition names; given an agent-owned or terminal step, then no
  transition is offered.
- Given the customer chooses a transition, then the item's `step` in its file is
  the target and the view reflects it.
- Given an item at `answering` with questions in its body, when the customer
  types answers and chooses `answered`, then the answers are in the body under
  their questions and the item is at `analysis`.
- Given an item moved to an agent-owned step, when the runner is active, then the
  owning agent is invoked without the customer leaving the TUI.
- [human] Given a captured story, when the customer takes it through analyse,
  answer, ready and play in one sitting, then each step and who holds it is clear
  throughout.
