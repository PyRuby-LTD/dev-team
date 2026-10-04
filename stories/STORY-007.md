---
id: STORY-007
type: story
title: "Work in the checkout on a branch per item, with the backlog on its own branch"
parent: EPIC-001
workflow: default
step: review
---

# Work in the checkout on a branch per item, with the backlog on its own branch

As the customer, I want to watch an item being implemented in the repository I
have open, take a cursory look, and then have an agent push it and open a pull
request, so I can see what is going on and the next item starts cleanly on its
own branch.

## Notes

This replaces the separate git worktrees per item introduced in STORY-002.

**Code.** Roles that change code work in the product checkout on branch
`devteam/<item id>`, created from the branch the checkout is on when the item
first reaches such a role. That base branch is remembered in git configuration
(`branch.devteam/<item id>.base`) so the reviewer can diff against it and the
runner can return to it. Replace the `worktree` role flag and the `clean`
command.

**One item in flight.** The item whose branch is checked out holds the checkout
until it reaches a terminal step. Any other item arriving at a code-changing
role waits and is reported as waiting. Steps that only edit work items, such as
analysis, are not held. When the holder is terminal, the runner switches to its
base branch and creates the next item's branch from there. If the checkout has
uncommitted changes when a switch is needed, the runner waits and says so
rather than switching.

**Backlog.** Work items must not move when code branches switch, so they live
on their own branch, `devteam-backlog`, in the same repository, checked out as a
git worktree at `backlog/` in the product root. The runner creates the branch
and worktree on first use, or attaches to an existing local or remote branch,
and keeps `backlog/` out of the code branches' status. The runner commits there
after every transition and after every agent step that edited an item, so the
branch history is the audit trail. Pull requests contain no live backlog files.
Agent transcripts stay untracked.

**Pull request.** Extend the default workflow:

```json
"accept":  {"owner": "human",           "transitions": {"pr": "publish", "accept": "done", "revise": "implement"}},
"publish": {"owner": "agent:publisher", "transitions": {"published": "done"}}
```

At `publish` the agent pushes `devteam/<item id>`, opens a pull request against
the base branch using the item's title and acceptance criteria, and records the
pull request URL in the item body. Add a `publisher` role to
`config/roles.toml` with a brief and a `prompts/publish.md`. Merging the pull
request remains the customer's decision. `accept` to `done` stays for
repositories with no remote.

**Record on the main branch.** Before pushing, a copy of the item file is
committed on the item's branch as `docs/work-items/<item id>.md`, so the record
of what was asked, answered, built and reviewed reaches the main branch when
the pull request is merged, and not if it is closed. The live item stays on the
backlog branch.

**This repository.** Move the items and notes in `workspace/` to the backlog
branch as part of this story, and point the commands at `backlog/`.
[STORY-006](STORY-006.md) then only has to make the product root the directory
the command is run in.

## Acceptance criteria

- Given a played item reaches the implementer, when the runner invokes it, then
  the product checkout is on `devteam/<item id>`, created from the branch it was
  on, and the agent's working directory is the checkout.
- Given the reviewer runs, then its prompt names the item's branch and the base
  branch recorded when the branch was created.
- Given one item between `implement` and a terminal step and a second played
  item, when the runner loops, then the second is not invoked and is reported as
  waiting for the first; an item at `analysis` is still run.
- Given the holding item reaches a terminal step, when the runner next loops,
  then the checkout returns to the base branch and the second item gets its own
  branch from it.
- Given uncommitted changes in the checkout when a branch switch is needed, then
  no switch happens, no agent is invoked and the reason is reported.
- Given a product repository with no backlog, when the runner or capture first
  runs, then `devteam-backlog` exists with no shared history with the code, it is
  checked out at `backlog/`, and `git status` on the code branch does not list it.
- Given any transition, when it is applied, then the backlog branch has one new
  commit naming the item, the transition and the target step.
- Given the code checkout switches between branches, then every item's `step` is
  unchanged.
- Given an item at `accept`, when the customer chooses `pr`, then the publisher
  is invoked; when it replies `published`, then the item is `done` and its branch
  contains `docs/work-items/<item id>.md`. Checked with a fake engine and a local
  bare repository as the remote.
- [human] Given a real GitHub repository, when the customer plays a story and
  chooses `pr` at `accept`, then a pull request exists against the base branch
  and the next played item starts on its own branch.
