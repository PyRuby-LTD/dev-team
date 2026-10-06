---
id: STORY-012
type: story
title: Return a rejected PR's comments to implement
parent: EPIC-003
workflow: default
step: captured
---
As the customer, I want a rejected PR's review comments passed back to implement, so that the implementer can address them without `gh` access.

## Acceptance criteria

- Moving to `rejected` reads every review body, inline review comment and conversation comment on the PR with `gh`.
- They are written under a `## Pull request feedback` heading in the item, replacing any earlier such section, and the item moves to `implement`.
- `prompts/implement.md` tells the implementer to address that section.
- If the `gh` call fails, the item stays at `rejected` and the error is shown.
