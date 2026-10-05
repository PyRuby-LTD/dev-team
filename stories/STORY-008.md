---
id: STORY-008
type: story
title: Stream agent output live to log and listener
parent: EPIC-001
workflow: default
step: ready
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

## Analysis

What exists today:

- `devteam/engines.py:run` uses `subprocess.run(capture_output=True)`, so nothing reaches the log until the process exits. It writes a header, stdout, then `# stderr` plus stderr. On `OSError` it logs and returns `(127, "")`. The reply is the whole of stdout.
- `Runner.invoke` (`devteam/runner.py`) calls `self.engine(role, prompt, cwd, extra_dir, log)` with exactly five positional arguments; tests inject fake engines with that signature (`tests/test_runner.py` `FakeEngine`). The reply's last line must be `TRANSITION: <name>`.
- There is no listener concept yet. The only outbound channel is `Runner.report`, which the TUI replaces (`devteam/tui.py:385`) with a thread-safe hop via `from_agents`. The agent loop runs on a background thread, so any listener must be called from that thread and marshalled by the TUI.
- `Role` (`devteam/config.py`) carries `command` and `permission` copied from the engine table; it has no `stream` field. `config/roles.toml` sets the claude engine to `--output-format text`. `devteam/render.py` does not exist.
- `claude` and `codex` are both installed locally, so the implementer can record real streams.

What would change:

- `engines.run` becomes a `Popen` loop. stdout and stderr must both be read concurrently (two threads, or stderr merged into stdout), otherwise a full pipe can deadlock. The stdout and stderr streams are tracked separately so the reply remains stdout only.
- `Role` gains `stream`, loaded from the engine table in `load_roles`. `roles.toml` gains `stream = "claude-json"` on the claude engine (with `--output-format stream-json --verbose`) and `stream = "text"` on codex.
- A new `devteam/render.py` holds the renderers and the claude-json reply extraction.
- `Runner` gains an optional `on_line` attribute, defaulting to `None`. It passes `on_line=` to the engine only when it is set. The TUI sets it.

Assumptions (stated, not questions):

- "Listener" means a single optional `Runner.on_line` callable taking one rendered line. The log keeps raw lines; the callback gets rendered lines. Wiring it into a TUI pane is not required by this story, only that the runner passes it through when set. If the TUI already displays something, the minimum is that setting `runner.on_line` works.
- stderr lines are interleaved into the log as they arrive. The existing `# stderr` section header is dropped in favour of live interleaving. For claude, stderr is never part of the reply.
- Stream-json lines are logged raw (JSON), per the "raw stream" criterion.
- An unknown `stream` value, or a missing key, falls back to `text`.

Gaps tightened below: the existing criteria are mostly checkable, but "listener", the exact result-event shape, and the codex split needed pinning down.

## Acceptance criteria

- `engines.run` reads the agent process line by line (stdout and stderr), appending and flushing each line to the log while the agent is still running. Test: a fake process that prints a line, then waits on a file or event, shows that line in the log before the process exits.
- `engines.run` accepts an optional `on_line` keyword (default `None`). It is called once per output line, from the stdout and stderr readers, while the process is still running. Test: a fake process that prints a line then blocks; the callback has received the line before the process is released.
- `Runner` has an optional `on_line` attribute (default `None`). It passes `on_line=` to the engine only when set. A fake engine with the existing five-argument signature still works unchanged when it is unset (existing `tests/test_runner.py` tests pass without edits).
- The `(code, reply)` return contract is unchanged: exit code of the process, `(127, "")` with a logged message when the binary cannot be started, and reply derived from stdout only. Runner reply handling (last-line `TRANSITION:`) and failure handling are unchanged.
- The claude engine in `config/roles.toml` uses `--output-format stream-json --verbose` and no `--include-partial-messages`. The reply is the `result` string of the final event with `"type": "result"`. If there is no result event, the reply is the concatenated text blocks of the `assistant` events. If there is neither, the reply is `""` and the returned code is non-zero (1 if the process exited 0, otherwise the process code is kept).
- Codex stdout and stderr are both streamed as printed through the `text` renderer. The reply for codex remains stdout only, as today. The implementer records in the PR or commit message which of the two codex prints its final message and progress on, from running the installed version.
- `Role` has a `stream` field loaded from a per-engine `stream` key in `config/roles.toml`. `claude` is `claude-json` and `codex` is `text`. `engines.run` selects the renderer and the reply extractor from `role.stream` via a lookup table, with no comparison against `role.engine` or an engine name. An unknown or missing value uses `text`.
- Renderers live in `devteam/render.py`. A renderer is a pure function from one raw line to a string or `None`/empty for "show nothing", and never raises, including on bad JSON, non-object JSON, missing keys and wrong types. For `claude-json`:
  - assistant text blocks are shown as text;
  - tool_use blocks are shown as `tool: <name> <short arg>`, where the short arg is the first of `file_path`, `path`, `command`, `pattern`, `url`, `description` present, else empty;
  - user/tool-result events and system/init events produce nothing;
  - lines over 200 characters are truncated with a trailing `...`;
  - unparseable lines are shown verbatim (subject to the same truncation).
- An exception raised by `on_line`, or by a renderer, is swallowed. It changes neither the returned code nor the reply, and the process is still drained to completion.
- The log file contains the header, then every raw line from the process in arrival order, including stderr lines, unrendered. A test compares the log body with the recorded input.
- Tests (`tests/test_engines.py` or `tests/test_runner.py`), using recorded streams stored as fixtures or inline strings: a successful stream, a stream with no result event, a stream with a malformed line, a non-zero exit, plus the fake-process timing test above. All run via `uv run python -m unittest` without needing `claude` or `codex` installed.
- The whole existing test suite still passes.

## Out of scope

Log viewer subcommand, partial-message token streaming, concurrent agents.
