---
id: REQUEST-001
type: request
title: As a customer using dev-team tui, I want to be able to see what an agent is
  curr
workflow: analysis
step: architect
---
As a customer using dev-team tui, I want to be able to see what an agent is currently doing, given an agent is working on a work-item. I want to be able to toggle this view so I can choose to watch the actions of one agent at a time, or not watch at all. I'm thinking it's basically like a tail -f of system out in a smaller pane, possibly the lower half of the right pane, auto-scrolling.

## Product owner findings

Audience: the customer running `devteam` TUI while agents work through items.

Problem: when an agent is working, the TUI shows only "started" and
"finished" lines in the bottom activity log. The customer cannot tell what the
agent is doing, whether it is stuck, or how long it will take.

Desired outcome: a live, auto-scrolling view of the active agent's output in
the lower half of the right-hand pane, which the customer can switch on and off.

What I found in the code (devteam/engines.py, runner.py, tui.py):
- `engines.run` uses `subprocess.run(capture_output=True)` and writes the log
  file only after the agent exits. Nothing exists to tail while it runs.
- The claude engine in `config/roles.toml` uses `--output-format text`, which
  emits only the final reply. Even with streaming of stdout, a claude agent
  would show nothing until it finishes. Live visibility needs a streaming
  output format (e.g. stream-json) and a way to render events as readable
  lines, while the final reply is still extracted for the transition line.
- The runner runs one agent at a time (`Runner.active` is a single item id), so
  "watch one agent at a time" currently means "watch the active agent". I assume
  agents stay serial; if concurrency is intended, say so.
- The right pane (`#detail`) shows the selected item's card and body; the
  `#activity` RichLog sits full-width at the bottom.

Assumptions (stated rather than asked):
- Toggle is a key binding (proposed `l`), shown in the footer; default is on
  whenever an agent is running, remembered for the session.
- The pane follows the currently running agent and labels it with item id,
  step and role. With nothing running it says so; it does not replay old logs.
- Auto-scroll sticks to the bottom; no search, filtering or log history UI.
- Output is shown as readable lines (assistant text, tool calls), not raw JSON.
- Out of scope: persistent logs UI, multi-agent concurrency, editing or
  interrupting the agent from the pane.

Proposed work (not yet captured, see blocker):
1. Story: stream agent output live to its log file and to a callback, keeping
   the exit code and final reply behaviour. Criteria: output lines appear in
   the log while the agent is still running; reply extraction and failure
   handling unchanged for both claude and codex engines; tests cover streaming
   with a fake engine.
2. Story: live agent pane in the TUI (parent of the same epic as other TUI work,
   likely EPIC-001 or a new one). Criteria: lower half of the right pane,
   auto-scrolls; toggle key shows/hides it and footer lists it; shows the
   active agent's item id, step and role; hidden pane costs no layout space;
   no stale output from a previous agent; tests in tests/test_tui.py.

Blocker: running `python3 -m devteam ... backlog capture` was refused for
approval in this session, so no work items have been created and there is
nothing to list under `## Created work items`. Architect input is requested
first because the streaming-format choice (stream-json vs plain text, and how
it affects the reply/transition parsing) shapes both stories.

Input needed from the architect: confirm the streaming approach for the claude
and codex engines, where the line-rendering belongs, and whether the log file
should hold the raw stream or rendered text.