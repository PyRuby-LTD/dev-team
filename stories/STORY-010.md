---
id: STORY-010
type: story
title: Hold a published item for the customer's PR decision
parent: EPIC-003
workflow: default
step: captured
---
As the customer, I want a published item to wait for my pull request decision, so that it is not shown as done before I have reviewed the PR.

## Acceptance criteria

- `publish` no longer moves the item to `done`; it moves to a human-owned step offering `merged` and `rejected`.
- The existing `accept` -> `done` path (no PR) is unchanged.
- The workflow definition validates.
- The tool does not merge or close the PR; the customer decides on GitHub and records the outcome by moving the item.
- `merged` and `rejected` are run by the harness, not an agent, via a new kind of harness-owned step beside `check`.
