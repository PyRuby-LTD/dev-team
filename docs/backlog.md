# Markdown work items

Work items live in `backlog/` at the root of the product repository, in
`epics/`, `stories/`, `tasks/` or `bugs/`. Other Markdown files are narrative, not items. Each item file starts
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
| `type` | Required `epic`, `story`, `task` or `bug`; must match its directory |
| `title` | Required nonempty string |
| `parent` | Story: an epic. Task: a story or bug. Bug: optional epic, story or task. Epic: none |
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

Each step has exactly one owner, `human` or `agent:<role>` where the role is
defined in `config/roles.toml`, and its transitions as name -> target step. A
step with no transitions is terminal. A definition with a missing or malformed
owner, an unknown role, a transition to an undefined step or a duplicate step
is rejected with a message naming the step.

An item whose `workflow` or `step` is not defined fails validation. Capture
puts a new item at its workflow's `initial` step. `move` applies one of the
current step's transitions and rewrites only the `step` line of the file.

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

Python 3.11+ and the pinned dependency in `requirements.txt` are required. Run
from the product repository, or pass `--product DIR` before the command:

```sh
python3 -m pip install -r requirements.txt
python3 -m devteam backlog capture epic 'Example'
python3 -m devteam backlog capture story 'Feature' --parent EPIC-001
python3 -m devteam backlog validate
python3 -m devteam backlog move STORY-001 analyse
python3 -m devteam run --once
python3 -m unittest discover -s tests -v
```

Use `--file` to supply the body and `--id` to choose an ID. `validate` lists
each item with its step and that step's owner, and exits 1 if any file has
errors. `run` invokes the owning agent for every item at an agent-owned step;
see the README. `tui` opens a two-pane view: the items on the left, and the selected
item's step, owner, valid transitions and rendered Markdown on the right. `y`
shows only what is waiting on you, `g` switches between grouping by epic and by
step, `tab` moves between the panes, and the files are re-read every two
seconds. It is built on Textual.
