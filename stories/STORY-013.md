---
id: STORY-013
type: story
title: Re-publish updates the existing PR
parent: EPIC-003
workflow: default
step: captured
---
As the customer, I want re-publishing after rejection to update the existing PR, so that I review one PR rather than several.

## Acceptance criteria

- When a PR already exists for the branch, the publisher pushes and updates it, records the same URL, and does not run `gh pr create` again.
- The `gh` calls the publisher needs are allow-listed in `config/roles.toml`.
