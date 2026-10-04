# Markdown work items

Work items live beneath a chosen root in `epics/`, `stories/`, `tasks/` or
`bugs/`. Other Markdown files are narrative, not items. Each item file starts
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

Workflow definitions are not loaded yet, so `workflow` and `step` are checked
only for presence and capture always writes `default` and `captured`. See
`workspace/stories/STORY-001.md`.

## Usage

Python 3.11+ and the pinned dependency in `requirements.txt` are required:

```sh
python3 -m pip install -r requirements.txt
python3 -m devteam backlog --workspace /tmp/example capture epic 'Example'
python3 -m devteam backlog --workspace /tmp/example capture story 'Feature' --parent EPIC-001
python3 -m devteam backlog --workspace /tmp/example validate
python3 -m unittest discover -s tests -v
```

Use `--file` to supply the body and `--id` to choose an ID. `validate` lists
each item with its step and exits 1 if any file has errors.

The `new/run/step/status/show/decide` commands still operate legacy ITEM
directories and do not read Markdown work items.
