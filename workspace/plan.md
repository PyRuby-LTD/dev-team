# Plan

Stories are numbered in build order. Each is played when the customer moves it
out of `ready`; the order below is a recommendation, not a commitment.

1. [STORY-001](stories/STORY-001.md): the workflow JSON and step transitions.
   Everything else reads it.
2. [STORY-002](stories/STORY-002.md): the runner. Prove it on the analysis step
   with a fake engine, then a real analyst.
3. [STORY-003](stories/STORY-003.md): the read-only terminal view. Needs only
   STORY-001, so it can be built alongside STORY-002.
4. [STORY-004](stories/STORY-004.md): actions in the terminal UI.
5. [STORY-005](stories/STORY-005.md): requests. A second workflow file and a new
   item type on the same runner and UI; no new mechanism.
6. [STORY-006](stories/STORY-006.md): launch from any product directory.

## Demonstration for EPIC-001

1. Open the TUI and enter a request. Answer questions from the product owner
   and any role it passes the request to, until it drafts work items; approve.
2. Pick one of the drafted stories; it is at `captured`, owned by the human.
3. Choose `analyse`; the analyst agent is invoked.
4. The analyst asks a question; the story moves to `answering`.
5. Answer it in the TUI and choose `answered`; analysis resumes.
6. The story reaches `ready` and stays there.
7. Choose `play`; the implementer is invoked.
8. Edit `workflows/default.json` to change an owner or transition and see the
   TUI and runner follow it without a code change.

## Already in place

`devteam/backlog.py` parses and validates the front matter and captures new
items. `config/roles.toml` and `devteam/engines.py` already map a role to an
engine and model and invoke it. The legacy pipeline (`pipeline.py`,
`workitem.py`, `state.json`) still exists and is retired by STORY-002.
