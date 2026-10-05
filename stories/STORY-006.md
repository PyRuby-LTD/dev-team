---
id: STORY-006
type: story
title: "Launch the team from any product directory"
parent: EPIC-002
workflow: default
step: captured
---

# Launch the team from any product directory

As the customer, I want to check out dev-team once, alias its launcher, and run
that command from any product repository, including an empty Git repository,
so the TUI opens for that product with the same team on every computer.

## Notes

Separate the harness root from the product root. Workflows, role briefs,
prompts and `config/roles.toml` resolve from the dev-team checkout; the product
root defaults to the directory the command is run in, replacing
`config/workspace`. Work items stay in the product as Markdown. Nothing may
depend on agents or skills in the user's home directory. Engine CLIs and their
credentials are prerequisites to document, not things to bundle.

## Acceptance criteria

- Given a dev-team checkout elsewhere and the documented alias, when it is run
  from a product directory, then the TUI opens on that directory's work items
  using the checkout's workflows, roles and prompts.
- Given an empty Git repository with no commits, when launched, then the TUI
  opens with an empty backlog and no agent is started.
- Given two product directories using one checkout, when items are changed in
  one, then the other product and the checkout are unmodified.
- Given a missing engine CLI or credentials, when an agent-owned step is run,
  then viewing still works and the failure is reported without moving the item.
- [human] Given a fresh checkout on another computer and the documented
  prerequisites, when the customer follows the setup, then it works without
  home-directory resources or source edits.

## Feedback

- **analyse -> analysis:** I use 'uv' for managing python. Include in the README.md instructions for creating an alias 'dev-team' in .bashrc that runs the dev-team tui in $PWD
