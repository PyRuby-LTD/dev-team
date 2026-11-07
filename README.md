# dev-team

**A product delivery team, defined as roles and workflows.** You describe what
you want; the roles question you, turn it into work items, implement them and
review them, and you decide what is played and what is merged.

This repository is the team. It is not about any particular product.

```
devteam/              the harness, its command line and the terminal UI
workflows/            the steps, their owners, outcomes and output shapes, as YAML
roles/                one brief per agent role
standards/            the rules and lenses analysis chooses for an item
prompts/              one Jinja template per agent-owned step, and example work items
views/                the template for the TUI's detail view
config/roles.toml     which engine and model each role uses, and the project check
```

The harness does one thing: it finds a work item whose current step the
harness or an agent owns, asks that step to perform, then validates and records
the step's outcome and output on the item and moves it to the step that outcome
leads to. Everything role-specific lives in the workflows, role briefs,
standards and prompts, so changing what a role does is an edit to those files,
not to the harness.

Work starts as a request, which the product owner analyses with you
(`workflows/request.yaml`) and divides into draft epics, stories, tasks and
bugs. Each of those then follows `workflows/default.yaml`.

Nothing is promoted automatically: `play` is an outcome only you can choose.

See [GLOSSARY.md](GLOSSARY.md) for the terms used here.

---

## Requirements

[`uv`](https://docs.astral.sh/uv/) supplies Python 3.13+ and the pinned
dependencies from `uv.lock`. You also need:

- `git` with `user.name` and `user.email` configured, and a GitHub `origin`
  for the product repository.
- The engine CLIs named in `config/roles.toml`: `claude` and `codex` by
  default, both signed in with your own subscription.
- `gh`, authenticated, for publishing and following pull requests, and
  permission to push to the product's `origin`.
- A product `Makefile` with a `regression` target (`make regression`,
  optionally `TEST=<name>`). `init` creates a placeholder that fails with an
  "unimplemented" message until you replace it.

Makefile targets must select the product's own environment (for a uv product,
use `uv run ...`), because `dev-team` runs `make` with the harness's virtual
environment inherited. Engine CLIs and credentials are prerequisites; they
are not bundled. The team uses this checkout's workflows, prompts, briefs,
standards and configuration, without agents or skills from your home
directory.

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

## Set up a product

`dev-team` acts on the directory it is run from, or the directory passed with
`--product DIR` before the subcommand. Run `dev-team init` first in a new
product:

```bash
cd /path/to/product
dev-team init
```

`init` requires an existing Git repository and a GitHub origin (HTTPS,
`git@github.com:owner/repo`, or `ssh://git@github.com/owner/repo`; other hosts
are refused). It refuses detached HEAD and `devteam/` item branches before
making changes. It creates a missing Makefile and sets up the backlog. In an
empty repository it commits only the Makefile on the current branch and pushes
that branch if it does not exist on origin. A rerun completes a failed commit
or push; an existing different origin commit produces a warning and no push. In
an existing codebase it makes no commit or push: it leaves a new placeholder
uncommitted and asks you to wire up `make regression` and commit. Existing
Makefiles are preserved, with a warning if they lack a regression target.

`tui` and `run` check this setup when they start, and refuse to run in a
product without a backlog branch or a regression target. They also load every
workflow first, so an invalid workflow is reported, naming the step and the
problem, before anything runs.

## The backlog

Work items are YAML files in `backlog/`, which is the `devteam-backlog` branch
checked out beside the code: `backlog/requests/`, `epics/`, `stories/`,
`tasks/` and `bugs/`. Every write is validated, then committed to that branch on
its own, so work-item changes never mix with product code. Machine paths, such
as your home directory, are masked in anything committed there; the original
is kept under `backlog/log/unmasked/` and a notice says so.

An item's requirements (overview, scope, acceptance criteria, questions and
their answers, chosen standards and so on) sit at its root. Every run of every
step appends an entry to its `step_outputs` with its outcome, the step it leads
to and what it produced. The entries addressed to an item's current step and
not yet passed are what that step must address. See
`prompts/examples/work-item.yaml` for every field an item can carry, and the
other files in `prompts/examples/` for each type.

The harness reads only `.yaml` items. Markdown items from the original harness
are left alone for you to triage by hand.

## Use

```bash
dev-team tui                      # the main way in
dev-team run [--once]             # perform agent and harness steps without the TUI
dev-team check [TEST]             # run the product's check, or one test
dev-team prompt [STEP] --item ID  # print the prompt each agent step would be given
dev-team --help                   # every command; each takes --help too
```

`tui` lists every item under its epic, with its step and who that step is
waiting on, and runs the harness behind it. An invalid item file is listed with
its error while the rest of the backlog still loads. Select an item to see its
requirements and the step outputs waiting on its current step, rendered from
`views/detail.md`.

When a step is waiting on you, press `enter` on it:

1. Any unanswered questions come first, each with a free-text answer box.
   Every question needs an answer; use n/a for one you cannot or will not
   answer.
2. At `ready`, a checklist of standards, pre-ticked with those analysis chose
   and their reasons. A standard you add is recorded as chosen by you.
3. A list of the step's outcomes, each with what it means.
4. Where the step takes feedback, a free-text box. Feedback reaches the owner
   of the step the outcome leads to.

Press `n` to capture a new request as free text, `y` to show only items
waiting on you, `tab` to switch pane, `r` to refresh and `q` to quit. A running
agent's output streams into the pane below the detail, prefixed with its item
ID, and the harness's activity is reported beneath that.

`run` keeps performing steps until interrupted; with `--once` it exits when no
step can move. `prompt` renders prompts without running an agent, for an item
in the backlog (`--item`), a work-item file (`--file`), or by default
`prompts/examples/work-item.yaml`; `--set name=value` fills in run values such
as `branch`.

The same outcomes you choose in the TUI can be recorded from the command line
with `dev-team backlog record ID OUTCOME`, with the step's output as YAML on
stdin.

## Workflows

A workflow is YAML: an `initial` step and a map of `steps`. Each step names its
`owner`, its `outcomes` (each with the `next` step and what it `means`), and
the shape of its `output`, as a JSON Schema or `requirements`. Agent steps also
name their `prompt`. Owners are:

- `human`: you, through the TUI. A customer step's output may only ask for
  questions, feedback or standards, since those are the inputs the TUI knows.
- `agent:<role>`: a role from `config/roles.toml`.
- `git:<Step>` or `harness:<Step>`: a step the harness performs itself.

Change an owner, an outcome or an output shape by editing the YAML; the harness
and the TUI follow.

`workflows/request.yaml`:

| Step | Owner | Outcomes |
|---|---|---|
| captured | you | `analyse` |
| analysis | product owner | `questions` (to answering), `drafted` (to review) |
| answering | you | `answered` (back to analysis) |
| review | you | `approve` (to done), `revise` (back to analysis) |
| done | - | |

While analysing, the product owner creates each draft with
`dev-team backlog create` and lists it in the request's `work_items`. When
revising, it updates existing drafts and takes unneeded ones out of the
request with a reason; it never closes them. Approved drafts wait at
`captured` in the default workflow until you choose to analyse them.

`workflows/default.yaml`:

| Step | Owner | Outcomes |
|---|---|---|
| captured | you | `analyse`, `wontfix` |
| analysis | product owner | `questions` (to answering), `analysed` (to challenge) |
| answering | you | `answered` (back to analysis) |
| challenge | challenger | `sound` (to ready), `rework` (back to analysis) |
| ready | you, choosing standards | `play` (to implement), `rework`, `wontfix` |
| implement | implementer, on the item branch | `implemented` (to test), `blocked` (to ready) |
| test | tester, on the item branch | `written` (to sync), `defect` (to implement) |
| sync | git | `completed` (to verify), `conflicted` (to resolve) |
| resolve | implementer | `resolved` (to verify), `blocked` (to ready) |
| verify | the project check | `passed` (to review), `failed` (to test) |
| review | reviewer, on the item branch | `approve` (to accept), `revise` (to implement) |
| accept | you | `pr` (to sync-publish), `revise` (to implement), `abandon` (to abandoning) |
| sync-publish | git | `completed` (to verify-publish), `conflicted` (to resolve-publish) |
| resolve-publish | implementer | `resolved` (to verify-publish), `blocked` (to ready) |
| verify-publish | the project check | `passed` (to publish), `failed` (to implement) |
| publish | publisher, on the item branch | `published` (to pull-request) |
| pull-request | git, and you | `merged` (to merged), `rejected` (to rejected), `abandon` (to abandoning) |
| merged | git | `completed` (to done) |
| rejected | harness | `completed` (to implement) |
| abandoning | git | `completed` (to abandoned) |
| abandoned, wontfix, done | - | |

The challenger attacks the analyst's work before you are asked to play it, and
runs on a stronger model. The reviewer should be a different engine from the
implementer; that independence is most of the value. Nothing is ever deleted
from the backlog: `wontfix` keeps a dropped item as a record.

## How an agent step runs

The harness renders the step's prompt from `prompts/` with the item, its
current step, the step outputs waiting on it and its chosen standards, followed
by the instructions for submitting. It runs the role's engine in the product
checkout with the role brief from `roles/<role>.md`, keeping the transcript
under `backlog/log/<item id>/`, and streams its output to the TUI.

Agents talk to the harness only through `dev-team backlog` commands, which the
rendered prompt gives with the full harness path:

- `submit ID OUTCOME`, with the step's output as YAML on stdin. It is checked
  at once and refused with the reasons if the outcome or output is invalid, so
  the agent can correct it before it exits. The last valid submission is the
  one recorded, once the agent has exited.
- `create TYPE TITLE` and `update ID`, with the item's fields as YAML on stdin.

An engine missing from the PATH, an engine exiting with an error, or an agent
exiting without a valid submission leaves the item at its step with the reason
reported. A failed item is not retried until the harness is restarted.

## Branches and the checkout

Roles marked `branch = true` change code. Before such a role runs, the harness
puts your checkout on `devteam/<item id>`, created from the branch you were on,
which it records as the item's base. You see the work happen in the repository
you have open. When the agent finishes, the harness commits what it changed to
that branch; agents are not expected to commit, since their sandboxes often
cannot write `.git`. Roles marked `push = true` have the branch pushed for them
first.

Only one step holds the checkout at a time: branch roles and git and check
steps. Others queue for it, and the TUI says which item they are waiting
behind. An item holds the checkout until it reaches a step that does not need
it, and the harness never switches branch over uncommitted changes; it waits and
says so. Steps that do not hold the checkout, such as analysis and challenge,
run alongside it and alongside each other.

`sync` and `sync-publish` fetch origin and rebase the item branch onto its
base. If rebasing conflicts, the harness aborts the rebase and merges the base
without committing, and `resolve` asks the implementer to resolve every
conflicted file. The harness commits the merge after `resolved`; `blocked`
aborts it. Later syncs keep an earlier merge from the base instead of replaying
its conflict.

Publishing pushes with `--force-with-lease` pinned to the last recorded remote
head, so rebased branches can be republished. Remote commits the harness has
not accounted for stop sync or publication with a message naming them; merge
them into the item branch by hand, or reset the remote branch, then retry.

At `pull-request` the harness checks the pull request with `gh` every minute
and moves on to `merged` once it has been merged. You may instead choose
`rejected` or `abandon`. Merging is yours to do; the harness neither merges nor
closes a pull request. At `merged`, the harness fetches origin and fast-forwards
the base branch before finishing at `done`. At `rejected`, it reads the pull
request's review, inline and conversation comments into the step's output for
the implementer. At `abandoning`, it switches the checkout back to the base,
keeping the item branch and its commits for recovery.

## The project check

Every product repository has a `Makefile` in its root with one target that
proves the system works: `make regression`, which also accepts `TEST=<name>` to
run a single test. It is named in `[check]` in `config/roles.toml`.

Agents never call `make`. Their prompts give them the harness command followed
by `check [<test>]`, which runs the target, prints a short result and keeps the
full output under `backlog/log/check/`. The `verify` steps are run by the
harness itself: the exit code chooses `passed` or `failed`, and that run, not
any agent's account, is what the reviewer is given.

Start and stop the app yourself in another terminal, including any local stubs
or databases it needs. The harness does not manage it.

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
`{harness_command}`. Prompts use `{{ harness_command }}` for the same command
derived from the checkout path, and role briefs may too.

Role briefs and standards are prose in the team author's own words; prompts
are templates to edit as you learn what each role gets wrong. Preview a change
with `dev-team prompt` before running anything.

## Before the first real run

- Confirm the codex model id in `config/roles.toml` against `codex exec --help`
  and your account.
- The engine templates have only been exercised with stub engines in the
  tests. Try one item on a throwaway repository and read `backlog/log/` first.
- Expect to hit subscription rate limits mid-run. Restart the harness once the
  window resets; every step resumes from the item file.
