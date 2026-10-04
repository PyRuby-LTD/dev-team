# dev-team

**A product delivery team, defined as roles.** Planning, analysis,
implementation, validation and the path to production - held as charters, the
skills that convene each role, and a pipeline that takes work items to a
reviewed change.

This repository is the team. It is not about any particular product. Point it
at one and it produces that product's artifacts in a workspace outside itself.

```
team/                 the roster - one charter per role, the source of truth
.claude/skills/       how to convene a role for an interview, in the main thread
.claude/agents/       the two roles that work without you: challenger, coherence
devteam/              the runner: reads each work item's step and invokes its owner
workflows/            the steps, their owners and valid transitions, as JSON
roles/ prompts/       role briefs, and one prompt per agent-owned step
config/workspace      where the current product's output goes
config/roles.toml     which engine and model each role uses
tools/workspace       point the team at a different product
examples/             a completed engagement, kept as a worked example
```

**Discovery** - five roles interview you: delivery manager, product owner,
architect, platform engineer, quality lead. They produce the problem, the
quality attributes, the architecture and its decisions, the platform, and a
first slice of stories with checkable acceptance criteria. Convene one with its
slash command: `/product-owner`, `/architect`, and so on.

**Delivery** - work items are Markdown files whose front matter names a workflow
and the item's current step. A workflow is JSON: each step has one owner, a
human or an agent role, and named transitions to other steps. The runner
invokes the owning agent for agent-owned steps by shelling out to coding agent
CLIs, and waits on human-owned ones. The rest of this file describes that half.

Nothing is promoted automatically - `play` is a transition only you can make.

---

## Requirements

`python3` (3.11+), `git`, and the CLIs named in `config/roles.toml` - `claude`
and `codex` by default, both signed in with your own subscription.

## Use

Run from the root of the product repository, or pass `--product DIR`:

```bash
python3 -m pip install -r requirements.txt
python3 -m devteam backlog capture story "CSV export drops the final row" --parent EPIC-001
python3 -m devteam tui                           # see items, answer questions, move them, run agents
python3 -m devteam backlog validate              # the same list, printed once
python3 -m devteam backlog move STORY-008 analyse
python3 -m devteam run --once                    # run agent-owned steps until none can run
python3 -m unittest discover -s tests -v
```

`tui` is the main way in: it shows every item, lets you answer an agent's
questions and choose a transition, and runs the agents once you press `s`.
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
| analysis | analyst | `questions` (to answering), `ready` |
| answering | you | `answered` (back to analysis) |
| ready | you | `play`, `rework` |
| implement | implementer, on the item's branch | `implemented` |
| review | reviewer, on the item's branch | `approve`, `revise` |
| accept | you | `pr` (to publish), `accept` (done, no pull request), `revise` |
| publish | publisher, on the item's branch | `published` |
| done | - | |

Change an owner or a transition by editing the JSON. The reviewer should be a
different engine from the implementer; that independence is most of the value.

## How an agent step runs

The runner renders `prompts/<step>.md`, appends the path of the work item and
the list of valid transitions, and invokes the owning role's CLI in the product
checkout with the role brief from `roles/<role>.md`. The agent reads the item,
may edit its body (questions, findings, implementation notes) but not its front
matter, and ends its reply with `TRANSITION: <name>`. The runner checks the name
against the step's transitions and moves the item.

A nonzero exit, a missing or unknown transition, or changed front matter leaves
the item where it is; the failure is printed with the path of the transcript
under `backlog/log/<item id>/`, and the item is not retried until the runner is
restarted. An item is run at most eight times per runner session, so a
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

At `accept`, look at the result in place. `pr` hands the item to the publisher,
which pushes the branch and opens a pull request against the base branch with
`gh`. Merging is yours to do.

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
`{cwd}` `{extra_dir}` (the workspace) `{permission}` `{max_turns}`.

Role briefs and step prompts are prose you should edit as you learn what each
role gets wrong.

## Before the first real run

- Confirm the codex model id in `config/roles.toml` against `codex exec --help`
  and your account; the default is a placeholder.
- The engine templates have only been exercised with a fake engine in the
  tests. Try one item on a throwaway repository and read `log/` first.
- The publisher needs `git push` access to `origin` and an authenticated `gh`,
  and the engine's permission mode must allow both.
- Expect to hit subscription rate limits mid-run. Restart the runner once the
  window resets; every step resumes from the item file.
