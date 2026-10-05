---
id: STORY-009
type: story
title: Live agent output pane in the TUI
parent: EPIC-001
workflow: default
step: captured
---
## Goal

The customer can watch the active agent's output live in the TUI, and switch the view on and off.

## Acceptance criteria

- An auto-scrolling RichLog occupies the lower half of the right-hand pane (`#detail`), sticking to the bottom, with `max_lines` of 2000.
- A key binding (proposed `l`) toggles the pane and is listed in the footer; the default is on while an agent runs and the choice is remembered for the session.
- When hidden, the pane takes no layout space and the item card gets the full right pane.
- A header shows the active agent's item id, step and role; with nothing running it says so and does not replay old logs.
- The pane is cleared when the active agent changes, so no stale output from a previous agent appears.
- The runner provides `on_output(item_id, line)` plus start/finish signalling carrying item id, step and role; lines reach the UI thread through the existing shutdown-safe helper.
- Lines are readable text (no raw JSON), supplied by the streaming story.
- Tests in `tests/test_tui.py` use a fake engine that emits lines.

## Depends on

The story "Stream agent output live to log and listener".

## Out of scope

Search, filtering, log history, interrupting the agent, concurrency.
