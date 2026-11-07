# 18: Push the item branch in a `git:Push` step, not as a role setting

**Type:** story

**Status:** needs-triage

**Blocked by:** 17

**As** the team's author
**I want** the push of an item's branch to be a harness step in the workflow
**So that** the workflow shows everything that happens to an item, and no role's configuration hides git behaviour inside an agent's step.

## Context

The publisher's role has `push = true` in `config/roles.toml`, so `AgentStep.perform` pushes the item branch before running the publisher. Agents often cannot write `.git` from their sandbox, which is why the harness pushes for them. The push, though, is invisible in the workflow. Its failure is reported as the publisher's step failing, and any role given `push = true` gains it silently.

A `git:Push` step, which the default workflow places between `record` (issue 17) and `publish`, makes the push explicit. `push = true` is then retired from the roles configuration.

## Acceptance Criteria

- [ ] **Given** an item that completes `record`, **When** the harness runs `push`, **Then** origin's branch for the item matches the local item branch, and the item moves to `publish` with `completed`.
- [ ] **Given** a remote branch with commits the harness has not accounted for, **When** `push` runs, **Then** the item stays at `push` with the foreign commits named, and nothing is pushed.
- [ ] **Given** a push that fails, for example because origin cannot be reached, **When** `push` runs, **Then** the item stays at `push` with the reason reported, and the publisher is not run.
- [ ] **Given** an item republished after a rejection and a later sync, **When** `push` runs, **Then** the rewritten branch replaces the remote one, leased to the head last pushed.
- [ ] `push` no longer appears in `config/roles.toml` or `Role`, and the publisher's step no longer pushes.

## Notes

- `Push` is a `GitStep` that produces only `completed` and holds the checkout. It reuses `git.push_branch`, which already leases against the recorded remote head and refuses foreign commits.
- The original runner still reads `role.push`. Leave that until issue 13 deletes the runner, or drop it here if nothing on the branch still drives the runner to a pushing role.
- The publish prompt already says that the harness has pushed the branch. Its wording needs no change.
- Journey test: `tests/redesign/test_publish_journey.py` already asserts that origin's branch matches the local one after publishing. Add the `push` entry to the expected history, and cover a failing push leaving the item at `push`.
