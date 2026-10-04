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
devteam/              the delivery pipeline: work item to reviewed change
roles/ prompts/       the delivery pipeline's own role briefs and stage prompts
config/workspace      where the current product's output goes
config/roles.toml     which engine and model each delivery role uses
tools/workspace       point the team at a different product
examples/             a completed engagement, kept as a worked example
```

**Discovery** - five roles interview you: delivery manager, product owner,
architect, platform engineer, quality lead. They produce the problem, the
quality attributes, the architecture and its decisions, the platform, and a
first slice of stories with checkable acceptance criteria. Convene one with its
slash command: `/product-owner`, `/architect`, and so on.

**Delivery** - a deterministic pipeline that takes one work item through intake,
investigation, implementation and review by shelling out to coding agent CLIs,
and stops for your decision before anything merges. The rest of this file
describes that half.

The seam between them is a story, carrying the acceptance criteria the pipeline
reviews against. Nothing is promoted automatically - you decide what enters the
pipeline and when.

---

## Requirements

`python3` (3.11+), `git`, and the CLIs named in `config/roles.toml` - `claude`
and `codex` by default, both signed in with your own subscription.

## Use

Markdown work items can be captured and validated separately from the legacy
delivery pipeline:

```bash
python3 -m pip install -r requirements.txt
python3 -m devteam backlog --workspace workspace validate
python3 -m unittest discover -s tests -v
```

See [the work item format](docs/backlog.md). Each item's front matter holds its
current workflow step. Running agents from that step and the terminal UI are
not implemented yet; see `workspace/stories/`. The commands below use legacy
ITEM directories.

```bash
python3 -m devteam new "The CSV export drops the final row" --repo ~/code/myapp
python3 -m devteam run ITEM-001        # runs until a gate or a failure
python3 -m devteam status
python3 -m devteam show ITEM-001       # state, per-stage engine, history
python3 -m devteam decide ITEM-001 approve -m "merged by hand"
python3 -m devteam clean ITEM-001      # drop the git worktree
```

`step` runs exactly one stage, which is the mode to use while you still want to
read everything. `run` loops until the pipeline needs you.

## Pipeline

| Stage | Role | Repository access | Advances when |
|---|---|---|---|
| intake | product owner | none | the request is answerable without further questions |
| investigate | analyst | read-only | the repository supports the request; writes acceptance criteria |
| implement | implementer | read-write, in a worktree | the criteria are satisfied |
| review | reviewer | read-only | the diff matches the criteria |

Review returning `revise` sends the item back to implement, bounded by
`max_revisions` in `state.json`. After that it is your call. `investigate`
returning `proceed: false` is a legitimate ending: the request was wrong.

The reviewer reads the diff, never `implementation.md`, and should be a
different engine from the implementer. That independence is most of the value.

## Work items

Everything an item knows lives in `work/ITEM-NNN/`:

```
request.md         what you asked for
intake.md          the product owner's reading of it
criteria.md        the contract review judges against
investigation.md   findings
implementation.md  what changed, and check output
review.md          findings against the diff
state.json         stage, status, per-stage engine history, your decisions
log/               every invocation: argv, and the full transcript
```

Implementation happens in a `git worktree` under `worktrees/`, on branch
`devteam/ITEM-NNN`, so a bad run is `devteam clean` rather than a mess in your
checkout. Nothing is merged for you.

## Choosing models per role

`config/roles.toml` maps each role to an engine and a model. Engines are
argv templates, so changing a flag does not mean changing code:

```toml
[roles.reviewer]
engine = "claude"
model = "sonnet"
```

Placeholders substituted per invocation: `{prompt}` `{model}` `{brief}`
`{cwd}` `{extra_dir}` (the work item directory) `{permission}` `{max_turns}`.
`{permission}` resolves through the engine's `permissions` table by the stage's
access level, so read-only stages get `plan` / `read-only` and write stages get
`acceptEdits` / `workspace-write`.

Role briefs are `roles/<role>.md`, passed as a system prompt. Stage prompts are
`prompts/<stage>.md` with `{{placeholder}}` substitution. Both are prose you
should edit as you learn what each role gets wrong.

## Before the first real run

- Confirm the codex model id in `config/roles.toml` against `codex exec --help`
  and your account; the default is a placeholder.
- Run `step` rather than `run`, on a throwaway repository, and read `log/`.
- Expect to hit subscription rate limits mid-pipeline. Every stage resumes from
  disk, so `step` again once the window resets.

## The actual experiment

`state.json` records which engine ran each stage and every decision you made at
a gate. After twenty items, that history says where you overrode the pipeline
and where you rubber-stamped it. Where you rubber-stamp, you are not adding
value; where you override, the stage prompt or the criteria are wrong. That is
the thing worth measuring, not whether the code compiles.
