# Markdown work items

Work items live in `backlog/` at the root of the product repository, in
`epics/`, `stories/`, `tasks/`, `bugs/` or `requests/`. Other Markdown files are narrative, not items. Each item file starts
with `---`, a YAML mapping and a closing `---` line, followed by a free-form
Markdown body.

```yaml
---
id: STORY-004
type: story
title: "Act on human-owned steps in the terminal UI"
parent: EPIC-001
workflow: default
step: ready
---
```

| Field | Contract |
| --- | --- |
| `id` | Required, unique within the root; uppercase type prefix then an identifier, e.g. `STORY-001` |
| `type` | Required `epic`, `story`, `task`, `bug` or `request`; must match its directory |
| `title` | Required nonempty string |
| `parent` | Story: an epic. Task: a story or bug. Bug: optional epic, story or task. Epic and request: none |
| `workflow` | Required except on epics: the name of the workflow definition the item follows |
| `step` | Required except on epics: the item's current step in that workflow |

`step` is the only state. Who owns a step and where an item may go next are
defined by the workflow, not by the item. Epics group work and carry neither
field. Questions, answers and acceptance criteria belong in the body; git
history is the audit trail.

Unknown fields, duplicate keys, YAML aliases, missing or mistyped parents,
parent cycles and duplicate IDs are reported per file. An item with an invalid
parent is reported too; unrelated items stay valid. Validation never writes.

## Workflows

A workflow is a JSON file in `workflows/`, named by the item's `workflow` field:

```json
{
  "initial": "captured",
  "steps": {
    "captured": {"owner": "human",         "transitions": {"analyse": "analysis"}},
    "analysis": {"owner": "agent:analyst", "transitions": {"ready": "ready"}},
    "ready":    {"owner": "human",         "transitions": {}}
  }
}
```

Each step has exactly one owner: `human`, `agent:<role>` where the role is
defined in `config/roles.toml`, or `check`, which the harness runs itself and
which has exactly the transitions `passed` and `failed`. Each step also has its
transitions as name -> target step. A step with no transitions is terminal. A definition with a missing or malformed
owner, an unknown role, a transition to an undefined step or a duplicate step
is rejected with a message naming the step.

An item whose `workflow` or `step` is not defined fails validation. Capture
puts a new item at its workflow's `initial` step. `move` applies one of the
current step's transitions and rewrites only the `step` line of the file.
Requests default to `analysis` / `submitted`; other moving types default to
`default` / `captured`. Step owners and transitions are resolved within each
item's workflow, so `review` can be human-owned in `analysis` and agent-owned
in `default`. Prompts use `prompts/<workflow>/<step>.md` when present and fall
back to `prompts/<step>.md`.

Request analysis is led by the product owner, who can ask questions, consult
the architect, platform engineer or quality lead, or complete analysis for
customer review. Specialists can ask questions or return to the product owner.
The request preserves the original text, questions, answers and findings.
Before completing, the product owner captures work with valid parents, lists
its IDs in the request body and validates it. Epics remain grouping items;
stories, tasks and bugs stay at their workflow's initial step. At request
review, `revise` returns to the product owner and `approve` ends the request.

## Where the backlog lives

`backlog/` is a git worktree of the `devteam-backlog` branch, which shares no
history with the code. The first `devteam` command run in a repository creates
the branch and the worktree, or attaches to an existing local or `origin`
branch, and lists `backlog/` in `.git/info/exclude` so the code branches do not
see it. Every capture and transition is committed there, so the branch history
is the audit trail and item steps do not move when the code checkout switches
branch. Agent transcripts under `backlog/log/` are ignored. Push the branch
with `git -C backlog push -u origin devteam-backlog`.

Outside a git repository, `backlog/` is a plain directory and nothing is
committed.

When an item is published, a copy of its file is committed on the item's code
branch as `docs/work-items/<id>.md`, so the record reaches the main branch when
the pull request is merged.

## Usage

`uv` is required; `uv sync` installs Python and the pinned dependencies. Run
from the product repository, or pass `--product DIR` before the command:

```sh
uv sync
uv run python -m devteam backlog capture epic 'Example'
uv run python -m devteam backlog capture request 'A new idea' --file idea.md
uv run python -m devteam backlog capture story 'Feature' --parent EPIC-001
uv run python -m devteam backlog validate
uv run python -m devteam backlog move STORY-001 analyse
uv run python -m devteam run --once
uv run python -m unittest discover -s tests -v
```

Use `--file` to supply the body and `--id` to choose an ID. `list` and `validate` list
each item with its step and that step's owner, and exits 1 if any file has
errors. `run` invokes the owning agent for every item at an agent-owned step;
see the README. `tui` opens a two-pane view: the items on the left, and the selected
item's step, owner, valid transitions and rendered Markdown on the right. It is
built on Textual and re-reads the files every two seconds.

| Key | Action |
| --- | --- |
| `n` | New request: enter text, then ctrl+s to capture it or esc to cancel. The first nonblank line becomes the title (up to 80 characters); the full text becomes the body |
| `enter` | On an item waiting on you: answer its questions or choose one of its step's transitions. When an agent takes over next, you are offered a note for it. On an item that is with an agent: leave a note for its next run, or override the step by choosing its outcome yourself |
| `s` | Start or stop the agents. They are stopped when the UI opens, so nothing is spent until you say so |
| `t` | Retry the selected item after its agent failed |
| `y` | Show only what is waiting on you |
| `g` | Switch between grouping by epic and by step |
| `tab` | Move between the list and the detail pane |
| `r` / `q` | Refresh / quit |

## Questions and answers

An agent asks the customer something by adding a numbered list under a
`## Questions` heading in the item body. Answers typed in the UI are written
beneath each question as `**Answer:** ...`; a question with such a line is
answered. Questions left blank stay unanswered.

## Feedback

When you move an item to an agent-owned step you can add a note, in the UI or
with `devteam backlog move <id> <transition> -m "..."`. It is appended to a
`## Feedback` section in the item body, labelled with the transition, and every
agent is told that the last entry there is why the item came to it.
