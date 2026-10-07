# dev-team

**A product delivery team, defined as roles and a workflow.** You describe what
you want; the roles question you, turn it into work items, implement them and
review them, and you decide what is played and what is merged.

This repository is the team. It is not about any particular product.

```
devteam/              the runner and terminal UI: reads each work item's step and invokes its owner
workflows/            the steps, their owners and valid transitions, as JSON
roles/                one brief per agent role
prompts/              one prompt per agent-owned step
config/roles.toml     which engine and model each role uses
docs/                 the work item format, and records of finished items
```

Work items are Markdown files whose front matter names a workflow and the
item's current step. A workflow is JSON: each step has one owner (a human, an
agent role, a project check or a harness action) and named transitions to other steps. The runner invokes the owning
agent for agent-owned steps by shelling out to coding agent CLIs, and waits on
human-owned ones.

Work starts as a request, which the product owner analyses with you and the
other roles (`workflows/analysis.json`) and turns into epics, stories, tasks and
bugs. Each of those then follows `workflows/default.json`.

Nothing is promoted automatically - `play` is a transition only you can make.

---

## Requirements

[`uv`](https://docs.astral.sh/uv/) supplies Python 3.13+ and the pinned
dependencies from `uv.lock`. You also need:

- `git` with `user.name` and `user.email` configured, and a GitHub `origin`
  for the product repository.
- The engine CLIs named in `config/roles.toml`: `claude` and `codex` by
  default, both signed in with your own subscription.
- `gh`, authenticated, for publishing, and permission to push to the product's
  `origin`.
- From the `test` step onwards, a product `Makefile` with a `regression` target
  (`make regression`, optionally `TEST=<name>`). `init` creates a placeholder
  that fails with an "unimplemented" message until you replace it.

Makefile targets must select the product's own environment (for a uv product,
use `uv run ...`), because `dev-team` runs `make` with the checkout's virtual
environment inherited. Engine CLIs and credentials are prerequisites; they
are not bundled. The team uses the checkout's workflows, prompts, briefs and
configuration, without agents or skills from your home directory.

## Set up the launcher

Check out dev-team once. From that checkout run:

```bash
uv sync
./install.sh
```

The installer checks prerequisites and appends the alias to `~/.bashrc`. Missing
uv or git is an error; missing git identity, engine CLIs or gh are warnings.
It installs no tools and does not check sign-in. An existing `dev-team` alias
is left unchanged with a warning, including one pointing to an old checkout.
Open a new bash shell or run `source ~/.bashrc`.

Alternatively, add this line to `~/.bashrc`, replacing `<checkout>` with the
absolute path to your dev-team checkout (run `uv sync` there first):

```bash
alias dev-team='uv run --project "<checkout>" python -P -m devteam'
```

The checkout path must contain no whitespace or any of `* ? [ ] ( ) " ' \`.
`--project` selects the harness environment while preserving your current
directory; `-P` prevents product files from shadowing harness dependencies.

## Use

`dev-team` is the alias for `uv run --project <checkout> python -P -m devteam`.
It acts on the directory it is run from, or the directory passed with
`--product DIR` before the subcommand. `dev-team help` lists the commands;
`dev-team backlog --help` describes the work item arguments. A bare `dev-team`
prints usage and exits nonzero.

Run `dev-team init` first in a new product. It requires an existing Git repository
and a GitHub origin (HTTPS, `git@github.com:owner/repo`, or
`ssh://git@github.com/owner/repo`; other hosts are refused). It refuses detached
HEAD and `devteam/` item branches before making changes. It creates a missing
Makefile and sets up the backlog. In an empty repository it commits only the
Makefile on the current branch and pushes that branch if it does not exist on
origin. A rerun completes a failed commit or push; an existing different origin
commit produces a warning and no push. In an existing codebase it makes no
commit or push: it leaves a new placeholder uncommitted and asks you to wire up
`make regression` and commit before opening the TUI. Existing Makefiles are
preserved, with a warning if they lack a regression target.

```bash
cd /path/to/product
dev-team init
dev-team help
dev-team backlog capture request "An idea for the product" --file idea.md
dev-team backlog capture story "CSV export drops the final row" --parent EPIC-001
dev-team tui                           # open the TUI
dev-team backlog validate
dev-team backlog move STORY-008 analyse
dev-team run --once                    # run agent-owned steps until none can run
dev-team check                         # run the product's checks
```

`tui` is the main way in: it shows every item, lets you answer an agent's
questions and choose a transition, and runs the agents once you press `s`.
Press `l` to show or hide live agent output below the item details. The pane
starts closed and keeps a continuous stream across runs, including output
received while hidden, bounded to the latest 2000 lines.
Press `n` to create a request from your text. Requests follow `analysis.json`:
move a submitted request with `analyse`, then the product owner asks questions
or consults the architect, platform engineer and quality lead. Each role's
questions return to that role after `answered`. The product owner captures
the resulting work items and lists their IDs in the request before handing it
to you at `review`. Choose `revise` to refine it or `approve` to finish. Created
work stays at its initial step until you choose to move it.
`move` applies a transition from the command line. `run` without `--once` keeps
watching for items that reach an agent-owned step.

Work items live in `backlog/`, which is the `devteam-backlog` branch checked out
beside the code; the first command creates it. See
[the work item and workflow format](docs/backlog.md).

## Workflow

`workflows/default.json`:

| Step | Owner | Transitions |
|---|---|---|
| captured | you | `analyse` |
| analysis | analyst | `questions` (to answering), `analysed` (to challenge) |
| challenge | challenger | `sound` (to ready), `rework` (back to analysis) |
| answering | you | `answered` (back to analysis) |
| ready | you | `play`, `rework` |
| implement | implementer, on the item's branch | `implemented` (to test), `blocked` (back to you at ready) |
| test | tester, on the item's branch | `written` (to verify), `defect` (back to implement) |
| verify | the harness runs `make regression` | `passed` (to review), `failed` (back to test) |
| review | reviewer, on the item's branch | `approve`, `revise` |
| accept | you | `pr` (to publish), `accept` (done, no pull request), `revise` |
| publish | publisher, on the item's branch | `published` (to pull-request) |
| pull-request | you | `merged` (to merged), `rejected` (to rejected) |
| merged | harness | `completed` (to done) |
| rejected | harness | `completed` (back to implement) |
| done | - | |

The implementer writes unit tests only where the logic is hard to get right;
the tester builds the regression suite, driving the running system against
canned data with as few mocks as possible. The challenger attacks the analyst's work before you are asked to play it, and
runs on a stronger model than the analyst. Change an owner or a transition by
editing the JSON. The reviewer should be a
different engine from the implementer; that independence is most of the value.

## How an agent step runs

The runner renders `prompts/<workflow>/<step>.md` when present, falling back to
`prompts/<step>.md`, then appends the path of the work item and
the list of valid transitions, and invokes the owning role's CLI in the product
checkout with the role brief from `roles/<role>.md`. The agent reads the item,
may edit its body (questions, findings, implementation notes) but not its front
matter, and ends its reply with `TRANSITION: <name>`. The runner checks the name
against the step's transitions and moves the item.

A nonzero exit, a missing or unknown transition, or changed front matter leaves
the item where it is; the failure is printed with the path of the transcript
under `backlog/log/<item id>/`, and the item is not retried until the runner is
restarted. An item is run at most sixteen times per runner session, so a
review/revise loop cannot continue unattended without limit.

## Branches

Roles marked `branch = true` change code, so the runner first puts your
checkout on `devteam/<item id>`, created from the branch you were on. You see
the work happen in the repository you have open. When the agent finishes, the
runner commits whatever it changed to that branch; agents are not expected to
commit, since their sandboxes often cannot write `.git`.

One item holds the checkout at a time: until it reaches a terminal step, any
other item that needs a code-changing role waits, while steps such as analysis
carry on. When the holder is finished, the runner returns to its base branch
and creates the next item's branch from there. It never switches branch over
uncommitted changes; it waits and says so.

At `accept`, look at the result in place. `pr` makes the runner push the branch to
`origin` and hands the item to the publisher, which opens a pull request against
the base branch with `gh`. Re-publishing after a rejection updates the existing
open PR's body and commits, preserving its title and URL. If no open PR exists,
the publisher creates one. The item then waits at `pull-request` for your decision
and continues to hold the checkout. Merging is yours to do; the tool does not
merge or close the PR. Choose `merged` to finish or `rejected` to return to
implementation, with an optional feedback note. At `merged`, the harness fetches
`origin`, switches to the recorded base branch, and fast-forwards it before
finishing at `done`. Local commits ahead of origin are kept. A dirty checkout
(including untracked files) or a base that has diverged from origin fails the
step before switching or moving any local branch. The item stays at `merged`
and holds the checkout, so other code-changing items wait. Fix the cause, then
press `t` in the TUI or call `Runner.retry(id)` to try again. At `rejected`, the
harness reads the PR's review, inline and conversation comments with `gh`, which
must be installed and authenticated. It replaces `## Pull request feedback`
before returning to `implement`. A failure leaves the item at `rejected`; fix
the cause and retry. Neither action changes the PR.

## The project check

Every product repository has a `Makefile` in its root with one target that
proves the system works: `make regression`, which also accepts `TEST=<name>` to
run a single test. It is named in `[check]` in `config/roles.toml`.

Agents never call `make`. Their rendered prompts supply the absolute harness
command followed by `check [<test>]`,
which runs the target, prints a short result and keeps the full output under
`backlog/log/check/`. A workflow step owned by `check` is run by the harness
itself: the exit code chooses `passed` or `failed`, and the result is written
into the item under `## Test run`. That run, not any agent's account, is what
the reviewer is given.

## Choosing models per role

`config/roles.toml` maps each role to an engine and a model. Engines are argv
templates, so changing a flag does not mean changing code:

```toml
[roles.reviewer]
engine = "claude"
model = "sonnet"
branch = true
```

Placeholders substituted per invocation: `{prompt}` `{model}` `{brief}`
`{cwd}` `{extra_dir}` (the backlog directory) `{permission}` `{max_turns}`
`{harness_command}`. Prompts and briefs use `{{harness_command}}` for the same
command derived from the checkout path.

Role briefs and step prompts are prose you should edit as you learn what each
role gets wrong.

## Before the first real run

- Confirm the codex model id in `config/roles.toml` against `codex exec --help`
  and your account; the default is a placeholder.
- The engine templates have only been exercised with a fake engine in the
  tests. Try one item on a throwaway repository and read `log/` first.
- Publishing needs `git push` access to `origin` for you, and an authenticated
  `gh` that the publisher's engine is permitted to run for PR lookup, creation
  and editing. Re-publishing after a rejection updates the existing open PR.
- Expect to hit subscription rate limits mid-run. Restart the runner once the
  window resets; every step resumes from the item file.
