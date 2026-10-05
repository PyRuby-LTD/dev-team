---
id: REQUEST-001
type: request
title: As a customer using dev-team tui, I want to be able to see what an agent is
  curr
workflow: analysis
step: product-owner
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
## Architect findings

Verified against devteam/engines.py, config/roles.toml, runner.py and tui.py. The product owner's reading is correct. `engines.run` uses `subprocess.run(capture_output=True)` and writes the log in one go after exit. The claude engine uses `--output-format text`, so there is nothing to tail until the agent finishes. The runner calls `engine(role, prompt, cwd, extra_dir, log)` and gets back `(code, reply)`. Tests inject fake engines through that signature.

### Recommended approach

1. **Streaming belongs in `engines.run`.** Replace `subprocess.run` with `Popen`, merge stderr into stdout (or read it on a second thread), and read line by line. Each line is appended and flushed to the log as it arrives. Each line is also passed to an optional `on_line` callback. The return contract `(code, reply)` stays, so the runner's reply and failure handling and the existing fake engines are untouched. `on_line` is an optional trailing parameter; the runner passes it only when a listener is registered, which keeps older fakes working.
2. **Claude engine: switch to `--output-format stream-json --verbose`.** `-p` mode requires `--verbose` for stream-json. Skip `--include-partial-messages`: whole assistant messages and tool calls per line are enough for "what is it doing", and token deltas would multiply the line volume for little gain. The reply is the `result` field of the final `{"type":"result"}` event, so `run` must extract it from the stream instead of returning raw stdout. If no result event arrives (crash, max-turns), return an empty reply with the non-zero code, which the runner already treats as a failure.
3. **Codex engine: stream what it already prints.** `codex exec` writes progress to stderr and the final message to stdout. Streaming both is enough for a tail view and needs no format change. `--json` would give structured events but it is a second parser to maintain for a role that is one of eight. I have not run codex here, so the implementer should confirm the stdout/stderr split on the installed version before relying on it.
4. **Engines declare their output format.** Add one per-engine key in `roles.toml`, for example `stream = "claude-json"` or `"text"`, which selects a small renderer function. Do not hard-code the engine name in `run`. This is the seam that keeps "swap engine/model freely" true.
5. **Rendering lives next to the parser, in a new `devteam/render.py` (or in `engines.py`).** The TUI should receive already readable lines and know nothing about JSON. Rendering turns assistant text into text lines and `tool_use` into `tool: Bash <short arg>`. It drops `system`/`user` tool-result noise by default, truncates long lines, and shows an unparseable line verbatim. The renderer must never raise on malformed JSON, because a stream failure must not fail the agent run.
6. **Log file holds the raw stream, not rendered text.** The raw log is the forensic record, so keep the format unchanged apart from the JSON lines. The renderer is pure, so the same lines can be re-rendered later if a log viewer is wanted. The cost is that existing logs for claude roles become JSONL, which is harder to read with `cat`. Mitigation: the runner's "see <log>" pointer stays the same, and a later small `devteam` subcommand could render a log. I recommend not building that now.

### Threading and data flow

The agent runs on a worker thread (`self.thread`, with `call_from_thread` for reports). The callback must hop to the UI thread the same way `report` does, using the existing shutdown-safe helper at tui.py:546. Output is bounded by the RichLog `max_lines` (suggest 2000) so a long run does not grow memory without limit. The TUI clears the pane when `Runner.active` changes, which gives "no stale output from a previous agent". The runner needs a second hook beside `report`, for example `on_output(item_id, line)`, plus a way to signal start and finish so the header (item id, step, role) can be set. Reusing `Runner.active` alone is not enough to know the step and role.

### Decisions and consequences

| Decision | Reversibility | Consequence |
|---|---|---|
| stream-json for claude | Cheap | Depends on the claude CLI event schema. If it changes, rendering degrades to raw lines, but the reply extraction could break and fail every claude run. Mitigate with a fallback: if no result event is found, use the concatenated assistant text. |
| Raw JSONL in the log file | Moderate | Existing tooling or habits that read the logs see JSON for claude roles. Anything parsing the logs elsewhere in the repo should be checked (I found none in runner.py). |
| Per-engine renderer in config | Cheap | One more config key; adding an engine means adding a renderer or using `"text"`. |
| Serial agents only | Moderate | The pane and `on_output(item_id, line)` assume one active agent. The item id on the callback keeps a later concurrent version possible without redesign. |

### Quality targets

- **Latency:** a line should reach the pane within about one second of the agent writing it. That is a loose target set by the human watching, not a measured requirement. Python's pipe buffering is the real risk, since `text=True` with a pipe to a child that fully buffers stdout would delay lines. claude and codex flush per event, so line-by-line reads are enough. A fake-engine test can assert that the callback fires before the process exits.
- **Volume:** a 30-60 turn agent produces hundreds to low thousands of lines. That is trivial for the log file and for a 2000-line RichLog. No storage or throughput concern.
- **Availability and failure:** a rendering or callback error must not change the agent's exit code or reply. Wrap the callback and catch exceptions in `run`.
- No target has been left without a consequence, so nothing to challenge here.

### Not a conflict

The customer's "tail -f of system out" and my "readable lines, raw log" choice agree: the customer sees readable lines in the pane, and the file is still the full stream.

### Suggested story split (for the product owner)

Same two stories as proposed, with a refinement: story 1 should carry the claude stream-json switch and reply extraction, and codex streaming with a renderer selected by config. It is the riskier story because a bad reply parse breaks every claude role, so it needs tests with recorded sample streams (success, no result event, malformed line, non-zero exit). Story 2 (the pane) can then use a fake engine that emits lines.

### Assumptions I am making (no answer needed unless the owner disagrees)

- Agents stay serial.
- Raw log is acceptable for claude roles being JSONL.
- No dependency changes are needed; `subprocess` and Textual's RichLog are enough.

No customer questions at this stage.
