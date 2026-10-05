---
id: STORY-006
type: story
title: "Launch the team from any product directory"
parent: EPIC-002
workflow: default
step: ready
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

## Analysis

What exists today (read from the code; the empty-repository launch was not run
here because the sandbox refused the scratch-directory commands):

- The harness/product split is largely done. `devteam/config.py` defines
  `ROOT` as the checkout; workflows (`workflow.py`), prompts (`runner.py`),
  role briefs and `config/roles.toml` all resolve from `ROOT`. The product
  root comes from `--product` (default `.`) in `cli.locate`, with work items in
  `<product>/backlog/`, a `devteam-backlog` worktree created by
  `git.ensure_backlog`. That path handles a repository with no commits
  (`worktree add --orphan`), and `tests/test_checkout.py` covers a fresh
  product.
- `config.workspace()`, `config/workspace` and `tools/workspace` are the
  leftover old mechanism. Nothing in `devteam/` calls `workspace()`; they are
  referenced only by the README, `team/README.md` and the five
  `.claude/skills/*/SKILL.md` files plus `.claude/agents/coherence.md`
  (discovery interviews, which still write to the configured workspace).
- Engine launch failure is already handled: `engines.run` catches `OSError`
  (missing CLI) and returns 127; the runner leaves the item in place and
  reports the transcript path. Whether a missing credential (CLI present,
  nonzero exit) behaves the same, and whether the TUI stays usable, is not
  covered by a test I could find.
- Nothing starts an agent on launch; `s` in the TUI does that.
- The README has no instruction for running from another directory. `main.py`
  is a stub. There is no console script in `pyproject.toml`.

What would change:

1. README: a setup section for a one-off checkout (`uv sync`), and the alias.
   Per the customer's feedback, use uv. The alias must keep the shell's
   working directory as the product and run the checkout's environment, so use
   `--project`, not `--directory`:
   `alias dev-team='uv run --project /path/to/dev-team python -m devteam tui'`
   in `~/.bashrc`. Replace the `python3 -m pip install -r requirements.txt` and
   `python3 -m devteam ...` examples with uv equivalents, and document the
   prerequisites (uv, git, `claude`/`codex` signed in, `gh` for publishing).
2. Retire `config/workspace` and `tools/workspace`: delete them and `workspace()`,
   and update the README layout list, `team/README.md`, the skills and the
   coherence agent to say the product root is the directory the command is run
   in. Skills under `.claude/` live in the checkout, not the home directory, so
   they satisfy the no-home-resources rule.
3. Tests for the criteria below that are not yet covered (empty repository
   launch, isolation between two products, missing credentials).

Assumptions I am comfortable with: the alias runs only the TUI, with other
subcommands still available through `uv run --project ... python -m devteam`;
`--product` stays as an override; the `backlog/` branch-worktree design is
unchanged; the discovery skills are only usable with Claude Code started in the
dev-team checkout, which is out of scope here.

Note on criterion 3: `ensure_backlog` adds `/backlog/` to the product's
`.git/info/exclude` and creates a worktree and branch in that product. That is
a modification of the product's git metadata, but not of the other product or
the checkout, which is what the criterion tests.

## Acceptance criteria

- The README documents, for a uv user, adding
  `alias dev-team='uv run --project <checkout> python -m devteam tui'` to
  `~/.bashrc`, with the checkout path shown as a placeholder, and states that
  the command acts on `$PWD`. (Checkable by reading the README.)
- README examples use `uv run`/`uv sync`, not `pip` or bare `python3`, and list
  the prerequisites: uv, git, the engine CLIs and their sign-in, and `gh` for
  publishing.
- Test: with `cwd` set to a product directory and the checkout elsewhere, the
  TUI/runner reads work items from `<product>/backlog` and loads workflows,
  prompts, role briefs and `roles.toml` from the checkout.
- Test: in a `git init` repository with no commits, `locate` plus a scan
  returns an empty backlog without error, and no engine is invoked (a fake
  engine records zero calls).
- Test: given two product repositories and one checkout, capturing and moving
  items in one leaves the other product's files and git status, and the
  checkout's `git status`, unchanged.
- Test: with the engine command missing, and separately with an engine that
  exits nonzero, running an agent-owned step leaves the item at its step,
  reports the failure with the log path, and a backlog scan still succeeds.
- `config/workspace`, `tools/workspace` and `config.workspace()` are gone, and
  `grep -r "config/workspace"` over tracked files returns nothing.
- No file under `devteam/` reads from `~` or `Path.home()`.
- The existing test suite passes (`uv run python -m unittest discover -s tests`).
- [human] Given a fresh checkout on another computer and the documented
  prerequisites, when the customer follows the setup, then it works without
  home-directory resources or source edits.

## Original acceptance criteria

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
