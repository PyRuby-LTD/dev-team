# Delivery-team harness engagement

This workspace holds the backlog for developing the reusable team harness
itself. It is selected by `../config/workspace`.

## Start here

- [Brief](brief.md): verbatim customer messages, ending with the simplification
  that the current backlog follows.
- [Scope](scope.md): what the first slice is and what is left out.
- [Plan](plan.md): build order and the demonstration that proves the slice.
- [Epics](epics/) and [stories](stories/): the backlog.

## Backlog conventions

Each work item is a Markdown file whose front matter is `id`, `type`, `title`,
`parent`, `workflow` and `step`. `step` is the item's only state; the workflow
definition says who owns that step and where the item can go next. Epics group
stories and have no step. Stories are numbered in build order; there is no
dependency field. See the [work item format](../docs/backlog.md).

`python3 -m devteam backlog --workspace workspace validate` checks the files
and lists each item's step.
