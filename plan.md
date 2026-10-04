# Plan

Each story is played when the customer moves it
out of `ready`; the order below is a recommendation, not a commitment.

1. [STORY-001](stories/STORY-001.md): the workflow JSON and step transitions.
   Everything else reads it.
2. [STORY-002](stories/STORY-002.md): the runner. Prove it on the analysis step
   with a fake engine, then a real analyst.
3. [STORY-007](stories/STORY-007.md): work in the checkout on a branch per item,
   backlog on its own branch, pull request on accept. Added after the others
   were numbered; build it before the TUI because it moves where items live.
4. [STORY-003](stories/STORY-003.md): the read-only terminal view. Needs only
   STORY-001, so it can be built alongside STORY-002.
5. [STORY-004](stories/STORY-004.md): actions in the terminal UI.
6. [STORY-005](stories/STORY-005.md): requests. A second workflow file and a new
   item type on the same runner and UI; no new mechanism.
7. [STORY-006](stories/STORY-006.md): launch from any product directory.

## Demonstration for EPIC-001

1. Open the TUI and enter a request. Answer questions from the product owner
   and any role it passes the request to, until it drafts work items; approve.
2. Pick one of the drafted stories; it is at `captured`, owned by the human.
3. Choose `analyse`; the analyst agent is invoked.
4. The analyst asks a question; the story moves to `answering`.
5. Answer it in the TUI and choose `answered`; analysis resumes.
6. The story reaches `ready` and stays there.
7. Choose `play`; the implementer is invoked on the item's own branch in the
   checkout. After review, take a look and choose `pr`.
8. Edit `workflows/default.json` to change an owner or transition and see the
   TUI and runner follow it without a code change.

## Already in place

- STORY-001: `devteam/workflow.py` loads `workflows/default.json`;
  `devteam/backlog.py` validates items against it, captures new items and
  applies transitions.
- STORY-002: `devteam/runner.py` invokes the owning role for agent-owned steps
  through `devteam/engines.py` and `config/roles.toml`. The legacy pipeline and
  its `state.json` items are gone.
- STORY-007: code-changing roles work in the checkout on `devteam/<item id>`,
  one item at a time; the backlog is on its own branch at `backlog/`; `pr` at
  `accept` hands the item to the publisher.
- STORY-003: `devteam tui` lists items under their epics with step and owner,
  and opens an item to read. It is read-only until STORY-004.
