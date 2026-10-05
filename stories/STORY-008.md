---
id: STORY-008
type: story
title: Stream agent output live to log and listener
parent: EPIC-001
workflow: default
step: captured
---
## Goal

While an agent runs, its output reaches the raw log file and a listener line by line, so it can be watched live.

## Acceptance criteria

- `engines.run` reads the agent process line by line (stdout and stderr), appending and flushing each line to the log while the agent is still running.
- An optional `on_line` callback receives each line; the runner passes it only when a listener is registered, so existing fake engines keep working.
- The `(code, reply)` return contract, runner reply handling and failure handling are unchanged for the claude and codex engines.
- The claude engine uses `--output-format stream-json --verbose` (no partial messages). The reply is the `result` field of the final result event; if there is no result event the reply falls back to concatenated assistant text, and if there is none the reply is empty with a non-zero code.
- Codex output (stdout and stderr) is streamed as it is printed; the implementer confirms the stdout/stderr split on the installed version.
- A per-engine `stream` key in `config/roles.toml` (for example `claude-json` or `text`) selects a renderer; the engine name is not hard-coded in `run`.
- The renderer lives in `devteam/render.py` (or `engines.py`), never raises, shows assistant text and `tool: <name> <short arg>` lines, drops tool-result noise, truncates long lines and shows unparseable lines verbatim.
- Errors in the callback or renderer never change the exit code or reply.
- The log file holds the raw stream.
- Tests use recorded streams (success, no result event, malformed line, non-zero exit) and a fake engine proving the callback fires before the process exits.

## Out of scope

Log viewer subcommand, partial-message token streaming, concurrent agents.
