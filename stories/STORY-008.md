---
id: STORY-008
type: story
title: Stream agent output live to log and listener
parent: EPIC-001
workflow: default
step: test
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

Stopped as instructed because the installed-version Codex stdout/stderr confirmation (review finding 2) cannot be completed in this environment. No implementation or test code was changed. Review finding 1 (multiline listener output) and the UTF-8 decoding defect reported under Tests remain unresolved. Completion requires a successful probe with service access, or a customer waiver of the channel-confirmation criterion.

Retried installed Codex 0.159.3 with temporary writable state under `/tmp`, a permission-restricted copy of the existing authentication file, closed stdin, and a 45-second timeout. The process exited before the timeout. Temporary state and authentication copy were removed automatically. stdout and stderr were captured separately: progress/errors appeared on stderr, stdout was empty, and no final agent message was produced. Its channel remains unconfirmed.

Probe command and actual result:

```text
codex exec --ephemeral --ignore-user-config --ignore-rules --sandbox read-only --skip-git-repo-check --cd /tmp 'Reply with exactly STREAM_SPLIT_OK. Do not use tools.'
exit: 1
stdout: ''
```

Actual stderr excerpts (repeated connection/reconnection messages omitted):

```text
WARNING: proceeding, even though we could not create PATH aliases: Refusing to create helper binaries under temporary dir "/tmp" (codex_home: AbsolutePathBuf("/tmp/story-008-codex-v8xrficx"))
Reading additional input from stdin...
2026-10-05T16:41:00.819579Z ERROR codex_models_manager::manager: failed to refresh available models: Connection failed: error sending request
OpenAI Codex v0.159.3
--------
workdir: /tmp
model: gpt-6.1-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: none
reasoning summaries: none
session id: 01a10cf0-9bd7-7b90-abfc-e144cc20214a
--------
user
Reply with exactly STREAM_SPLIT_OK. Do not use tools.
2026-10-05T16:41:03.889652Z ERROR rmcp::transport::worker: worker quit with fatal: Transport channel closed, when Client(HttpRequest(HttpRequest("http/request failed: error sending request for url (https://chatgpt.com/backend-api/ps/mcp)")))
warning: Falling back from WebSockets to HTTPS transport. workspace routing discovery failed
ERROR: workspace routing discovery failed
ERROR: workspace routing discovery failed
```

Checks run directly, with actual output:

```text
$ UV_CACHE_DIR=/tmp/story-008-uv-cache uv run python -m unittest tests.test_engines tests.test_runner tests.test_streaming.StreamingThroughRun.test_output_that_is_not_utf8_does_not_truncate_the_reply
.................F
======================================================================
FAIL: test_output_that_is_not_utf8_does_not_truncate_the_reply (tests.test_streaming.StreamingThroughRun.test_output_that_is_not_utf8_does_not_truncate_the_reply)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/tarttelin/projects/pyruby/dev-team/tests/test_streaming.py", line 75, in test_output_that_is_not_utf8_does_not_truncate_the_reply
    self.assertEqual("answering", self.step())
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: 'answering' != 'analysis'
- answering
+ analysis


----------------------------------------------------------------------
Ran 18 tests in 0.876s

FAILED (failures=1)

$ git diff --check
(no output; exit 0)
```

The full suite remains for the tester/harness, as requested. No commits were made.

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

Not covered end to end: the Codex stdout/stderr split (unconfirmed, review finding 2), rendering and truncation, and multi-line listener output (review finding 1); the renderer is only reachable through `on_line`, which only unit tests in `tests/test_engines.py` exercise.

Defect: `test_output_that_is_not_utf8_does_not_truncate_the_reply` fails. The recorded stream `tests/fixtures/streams/invalid_utf8.jsonl` has the bytes `\xe9 \xff` in an assistant text block, then a valid result event ending `TRANSITION: questions`. Expected the step to move to `answering`; it stays at `analysis`. Cause: `engines.run` opens the pipes with `text=True` and strict decoding, so the stdout reader thread dies on `UnicodeDecodeError`, the reply is lost and nothing is logged. Fix by decoding with `errors="replace"` (for example `encoding="utf-8", errors="replace"` at `devteam/engines.py:40`). Confirmed again on the latest run: 89 tests, this is the only failure.

## Review

Findings, most damaging first.

1. Rendered output is not one line per `on_line` call. Trigger: an assistant text block of several lines, or a `tool_use` whose `command` contains newlines (any multi-line Bash command or heredoc). `claude_json` joins the parts with a newline and returns one string, so `on_line` gets a multi-line string, and an embedded newline in the short arg is passed through untouched. Truncation is applied per part, not to the whole string. The story is "a listener line by line" and the analysis defines `on_line` as taking "one rendered line". A line-oriented consumer, such as a TUI pane appending one row per call, will mis-render. Fix: collapse whitespace in the short arg, and have `run` call `on_line` once per rendered line, or have the renderer return a list. Add a test with a multi-line command and a multi-line text block.

2. Codex criterion is not met. The criterion requires confirming which of stdout and stderr carries codex's final message and progress on the installed version, and recording it. The implementer reports that `codex` could not initialise in their environment and that nothing was confirmed. It is honestly reported, but it is still unmet. Codex reply handling stays stdout-only on an unverified assumption. If the final message goes to stderr, the reply will be empty. Fix: probe in an environment where codex starts, and record the result in the commit message or the item. If that is impossible, the customer has to waive the criterion.

3. Minor robustness: a `UnicodeDecodeError` in a reader thread (`text=True`, strict decoding) kills that thread silently. The reply is truncated and the pipe is closed on the child with no logged error. Previously the call raised. Consider `errors="replace"`.

4. Minor test weakness: `test_log_holds_the_raw_stream_including_stderr` in `tests/test_streaming.py` strips the stderr text before comparing, so it does not check ordering. The exact-match comparison in `tests/test_engines.py` covers ordering, and only for the separate-pipe case.

Criteria found satisfied, with evidence:
- Line-by-line flushed log: the `engines.run` drain loop writes and flushes per line. `test_both_pipes_reach_log_and_listener_before_exit` and the stub's `STUB_AWAIT_LOG` test prove it against real processes.
- Optional `on_line` in `run`: called while the process is running, proven by the same ack test.
- `Runner.on_line` passed only when set: `runner.py` builds `options` conditionally. `test_runner_passes_registered_listener` covers the set case, and the existing five-argument fakes pass.
- Return contract: 127 with a logged message is covered by `test_missing_binary_fails_the_step_with_a_logged_message`. The exit code is kept, as `test_non_zero_exit_code_is_kept_and_fails_the_step` shows. The reply is stdout only.
- Claude engine args: `roles.toml` has `stream-json --verbose` and no partial messages, and a test asserts it. The result, assistant-text fallback and empty-with-non-zero-code behaviours are all tested.
- `stream` key: loaded by `Role.stream` and looked up in the `STREAMS` table with a `text` fallback. There is no engine-name comparison, and a test uses the engine name `arbitrary-name`.
- Renderer never raises, drops user and system events, truncates to 200 characters and shows bad lines verbatim: the `Rendering` tests cover these. Multi-line behaviour is the exception, see finding 1.
- Exceptions in the callback or renderer are swallowed: `test_display_failures_do_not_change_reply`.
- The raw log holds the header, then the lines in arrival order.
- Recorded-stream tests need no installed claude or codex.
- Whole suite: the harness run passed, 88 tests.

Verdict: revise. Findings 1 and 2 block approval.

## Test run

Run by the harness, 2026-10-05 16:30 UTC. Full output: `/home/tarttelin/projects/pyruby/dev-team/backlog/log/STORY-008/verify-20261005T162938542801.log`

Passed: `the project check`

```text
uv run python -m unittest discover -s tests
........................................................................................
----------------------------------------------------------------------
Ran 88 tests in 26.871s

OK
```
