---
id: STORY-003
type: story
title: "See work items and their steps in a terminal UI"
parent: EPIC-001
workflow: default
step: implement
---

# See work items and their steps in a terminal UI

As the customer, I want a terminal view of every work item and the step it is
in, so I can see what is waiting on me and what the agents are doing.

## Notes

Add `devteam tui`. List the stories, tasks and bugs grouped under their epic,
each showing its step and that step's owner from the workflow JSON. Mark the
items whose step is human-owned as needing the customer. Selecting an item
shows its Markdown body. The view is read from the files each time; there is no
cache or separate state.

## Acceptance criteria

- Given a backlog with items at several steps, when the TUI opens, then each item
  shows its ID, title, step and owner, grouped under its epic.
- Given items at human-owned steps, then they are distinguishable from
  agent-owned and terminal ones by text, not colour alone.
- Given an item file changes on disk, when the view refreshes, then the new step
  is shown.
- Given a file with invalid front matter, then it is listed with its error and
  the other items remain usable.
- [human] Given the default workflow, when the customer browses by keyboard, then
  they can find what needs them and read any item without opening the raw file.
