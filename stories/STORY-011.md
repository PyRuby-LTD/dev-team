---
id: STORY-011
type: story
title: Bring local main in line with origin when a PR is merged
parent: EPIC-003
workflow: default
step: captured
---
As the customer, I want local main brought in line with origin when I mark a PR merged, so that my checkout reflects what I merged.

## Acceptance criteria

- Moving to `merged` fetches origin and fast-forwards the base branch.
- The item ends at a terminal step.
- If main has diverged or the checkout is dirty, the step fails with a message naming the cause and leaves the repository untouched.
- Tested against a local bare remote.
