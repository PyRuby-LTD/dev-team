---
id: STORY-008
type: story
title: Stream agent output live to log and listener
parent: EPIC-001
workflow: default
step: publish
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

## Implementation

Implemented review findings 1 and 3 and the decoding defect reported under Tests.

- `devteam/engines.py` delivers each rendered line separately to `on_line`. Callback exceptions are swallowed per line so later lines from the same event still reach the listener; renderer exceptions still leave the raw log and reply intact.
- `devteam/render.py` collapses whitespace in tool names and short arguments, including multiline commands, before applying the existing 200-character truncation. Assistant text remains split and truncated per displayed line.
- Process pipes now use UTF-8 with `errors="replace"`, so invalid bytes cannot kill a reader and discard subsequent result events. Invalid bytes appear as replacement characters in the unrendered transcript.
- Added a real-process unit test for multiline assistant text and tool commands, truncation, raw-log preservation, and a failing listener followed by successful callbacks. Added a renderer assertion for a multiline command.

Review finding 2 is resolved by the customer's latest Feedback: the installed Codex version's final message is on stdout and progress is on stderr, confirmed from the runner's own logs. No Codex probe was run. Review finding 4's ordering assertion is already present in the current `tests/test_streaming.py`; no tester tests were changed.

Checks run directly, with actual output:

```text
$ UV_CACHE_DIR=/tmp/story-008-uv-cache uv run python -m unittest tests.test_engines tests.test_runner tests.test_streaming.StreamingThroughRun.test_output_that_is_not_utf8_does_not_truncate_the_reply
...................
----------------------------------------------------------------------
Ran 19 tests in 1.120s

OK

$ git diff --check
(no output; exit 0)
```

No failures in these checks. The full suite is left to the tester/harness as requested. No commits were made; changes remain in the working tree.

## Tests

Black-box tests in `tests/test_streaming.py` run `python -m devteam --product <tmp> run --once` against a stub `claude` executable (`tests/stubs/claude`, copied onto PATH) that replays recorded streams from `tests/fixtures/streams/`. The listener (`on_line`) is not reachable from the CLI, so its criteria are covered only by the implementer's unit tests in `tests/test_engines.py`.

| Criterion | Test |
| --- | --- |
| Lines appended and flushed to the log while the agent runs | `test_first_line_is_in_the_log_while_the_agent_is_still_running` (the stub exits 99 unless its first line is in the log before it finishes) |
| Return contract, 127 on a missing binary | `test_missing_binary_fails_the_step_with_a_logged_message` |
| Non-zero exit kept; failure handling unchanged | `test_non_zero_exit_code_is_kept_and_fails_the_step` |
| Claude uses `stream-json --verbose`, no partial messages | `test_claude_is_invoked_with_stream_json_and_no_partial_messages` |
| Reply is the `result` event | `test_result_event_is_the_reply_that_drives_the_transition` |
| Fallback to assistant text | `test_assistant_text_is_the_reply_when_there_is_no_result_event` |
| Neither: empty reply, non-zero code | `test_stream_without_result_or_text_fails_the_step` |
| Malformed line tolerated and shown raw | `test_malformed_line_is_logged_verbatim_and_does_not_break_the_reply` |
| Log holds header then the raw stream, stderr first and in order (review finding 4) | `test_log_holds_the_raw_stream_including_stderr` |
| Non-UTF-8 output does not truncate the reply (review finding 3) | `test_output_that_is_not_utf8_does_not_truncate_the_reply` |
| `stream` key in roles.toml selects the claude-json reply handling | the result and fallback tests above, driven by the real `config/roles.toml` |

Run one on its own: `uv run python -m devteam check tests.test_streaming.StreamingThroughRun.test_non_zero_exit_code_is_kept_and_fails_the_step`

| Codex: stdout is the reply, stderr progress is logged, `text` stream | `tests.test_streaming.CodexStreamingThroughRun.test_codex_reply_is_stdout_and_progress_on_stderr_is_logged` (stub `tests/stubs/codex` prints the final message on stdout, then progress on stderr; the step only transitions if the reply excludes stderr) |

The Codex test runs the implement step in a throwaway git repository with only git, python3 and the stub on PATH, so the following tester step fails fast instead of starting a real claude.

Not covered end to end: rendering, truncation and multi-line listener output. The listener (`on_line`) is not reachable from the CLI, so these are covered only by the implementer's unit tests in `tests/test_engines.py`.

Whole suite: 93 tests pass via `uv run python -m devteam check`. The earlier non-UTF-8 defect is fixed.

## Review

No blocking findings. Earlier findings 1 (multi-line rendering), 2 (Codex split, resolved by customer feedback: final message on stdout, progress on stderr) and 3 (non-UTF-8) are addressed.

Minor, not blocking:

1. `claude_json` returns `None` for any valid non-object JSON line (for example a bare `42`), so it is hidden rather than shown verbatim. Such lines are parseable, so this is arguably per the spec, but a stray line vanishes from the listener. The raw log is unaffected.
2. The Codex split is covered end to end only by a stub, which encodes the customer's statement rather than the real binary. Acceptable given the feedback.

Criteria satisfied, with evidence:
- Line-by-line flushed log: `drain` in `engines.run` writes and flushes per line under a lock. `test_first_line_is_in_the_log_while_the_agent_is_still_running` and `test_both_pipes_reach_log_and_listener_before_exit` use real processes.
- Optional `on_line`, called while running, once per line: `run` splits the rendered output and calls per part. `test_multiline_text_and_command_reach_listener_as_individual_lines` covers multi-line text and commands.
- `Runner.on_line` passed only when set: `runner.py` builds `options` conditionally. `test_runner_passes_registered_listener` covers the set case, and the existing five-argument fakes pass.
- Return contract: 127 with a logged message (`test_missing_binary_fails_the_step_with_a_logged_message`), exit code kept (`test_non_zero_exit_code_is_kept_and_fails_the_step`), reply from stdout only.
- Claude engine: `roles.toml` has `stream-json --verbose`, no partial messages (asserted). Result, assistant-text fallback and empty-with-non-zero-code are each tested.
- Codex streamed through the `text` renderer, reply stdout only: `test_codex_reply_is_stdout_and_progress_on_stderr_is_logged`.
- `stream` key: `Role.stream` loaded from the engine table, looked up in `STREAMS` with a `text` fallback, no engine-name comparison.
- Renderer never raises, drops user/system events, truncates to 200, shows bad lines verbatim (`test_event_shapes_and_truncation`, `test_reply_ignores_wrong_types`).
- Callback and renderer exceptions swallowed per line without changing code or reply: `test_display_failures_do_not_change_reply`.
- Raw log holds the header and raw lines in arrival order, including stderr: `test_recorded_stream_replies_and_raw_log`, `test_log_holds_the_raw_stream_including_stderr`.
- Recorded-stream tests need no installed claude or codex. Whole suite: harness run passed, 93 tests.

Verdict: approve.

## Test run

Run by the harness, 2026-10-05 17:01 UTC. Full output: `/home/tarttelin/projects/pyruby/dev-team/backlog/log/STORY-008/verify-20261005T170038488550.log`

Passed: `the project check`

```text
uv run python -m unittest discover -s tests
..........................................................................Executing <Task pending name='message pump Actions()' coro=<MessagePump._process_messages() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/message_pump.py:571> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.119 seconds
.....Executing <Task pending name="message pump Screen(id='_default')" coro=<MessagePump._process_messages() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/message_pump.py:571> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.103 seconds
..............
----------------------------------------------------------------------
Ran 93 tests in 31.459s

OK
```

## Feedback

- **note at implement:** The Codex stdout/stderr split is confirmed from the runner's own logs: the final message is on stdout and progress on stderr. Do not probe Codex. Fix review findings 1 and 3.
