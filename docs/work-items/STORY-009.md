---
id: STORY-009
type: story
title: Live agent output pane in the TUI
parent: EPIC-001
workflow: default
step: publish
---
## Goal

The customer can watch the active agent's output live in the TUI, and switch the view on and off.

## Analysis

### What exists today

- The dependency is already met. `engines.run` takes `on_line` and calls it with readable text per line (rendered by the role's stream renderer, not raw JSON); listener exceptions are swallowed. `Runner.on_line` (`devteam/runner.py`) is a plain attribute, default `None`, passed to the engine only when set. Its signature is `on_line(line)`. That is all the pane needs: it shows a bare stream with no header or per-run label (Q2, Q4), so nothing consumes an item id. `on_line` is set only in `tests/test_engines.py:127` and read only at `runner.py:237`; `devteam/cli.py` does not touch it.
- `Runner.active` holds the item id while `invoke` runs an agent (set before the engine call, cleared in `finally`) and also while `Runner.verify` runs the project check (`runner.py:268`); the tree and card show "running" for both. `checks.run` captures output with `subprocess.run` and has no line callback, so a check step streams nothing. Step and role are not recorded. `report(message)` is how the runner already talks to the TUI.
- `devteam/tui.py`: `Backlog.compose` yields `Horizontal(ItemTree #items, VerticalScroll #detail [Static #card, Markdown #body])`, then a full-width `RichLog #activity` (height 7) below it. `#activity` shows runner `report` messages and its border title is the "Agents: running/stopped" status. `from_agents(callback, *args)` is the shutdown-safe helper (checks `is_running`, swallows `RuntimeError` from `call_from_thread`). `BINDINGS` uses n y g s t tab r q, so `l` is free. `check_action` disables app bindings while a modal is open.
- `#detail` is the focus target of `action_switch_pane` and is asserted in `tests/test_tui.py:143` (`query_one("#detail").has_focus`). The agent test fixture (`tests/test_tui.py` ~line 211) builds a real `Runner` with a fake engine, but its engine signature needs changing (see below).
- Nothing in the TUI uses `runner.on_line` yet. `tests/test_engines.py` (~line 122-127) sets `runner.on_line`.
- The `Acting` fixture's engine (`tests/test_tui.py:214`) is `engine(self, role, prompt, cwd, extra_dir, log)` with no `on_line`. The runner passes `on_line` only when a listener is set (`runner.py:237`), so once the TUI registers a listener every TUI-driven run would raise `TypeError` in that fixture, which `run_item` does not catch. The two existing agent tests (around lines 412 and 424) would fail. The fixture must change.

### What would change

1. `devteam/runner.py`: unchanged. The TUI uses the existing `Runner.on_line`. There is no start or finish hook: the customer wants output left on screen and one continuous stream across runs (Q2, Q4). `Runner.verify` fires no hook (Q3). Listener exceptions are already swallowed by `engines.run` (`engines.py:61-64`), and `from_agents` swallows the shutdown `RuntimeError`, so no new wrapper is needed.
2. `devteam/tui.py`: put `#detail` and the new output pane in a `Vertical` right-hand column. The pane is a single `RichLog #output` (`auto_scroll=True`, `max_lines=2000`, `markup=False`, `wrap=True`, `min_width=1`) with no header, border title or status text: it is only the agent's stream (Q2). `#detail` keeps its id and focus behaviour. In `on_mount`, beside the existing `runner.report` assignment (`tui.py:408`), set `self.runner.on_line = lambda line: self.from_agents(self.agent_output, line)`; `agent_output` appends to the deque while hidden and writes to the log while shown. The pane starts hidden (`display = False`). Add binding `l` to `BINDINGS` (so it appears in the footer) that toggles `display`.
   Why `min_width=1` (checked in Textual 8.2.8, `_rich_log.py:221-247`): a written line is rendered at `max(min(line width, pane content width), min_width)` and `min_width` defaults to 78. Left at the default, a half-width pane (under 60 columns at 120 wide, under 40 at 80 wide) wraps at 78 and the tail of every long line is off screen. `render.py` lets lines reach 200 characters, so this would bite.
   Why the TUI buffers while hidden: until the log has had a non-zero width once, `write` only queues (`_rich_log.py:205-213`) and the queue is rendered on first resize. After that, `write` renders at once at `scrollable_content_region.width`, which I expect to be 0 for a hidden widget, so with `min_width=1` every character would land on its own row, and a line is never re-wrapped. I could not run a probe in this session, so this is reasoned from the source, not observed. The remedy does not depend on the answer: while `#output` is hidden the TUI appends lines to its own `collections.deque(maxlen=2000)` and does not write them to the log; showing the pane writes the buffered lines in order and empties the buffer. The flush must not happen in the `l` action straight after `display = True`: layout has not run, so a re-shown log (whose size is already known) would render at whatever width a hidden widget reports. Flush after layout, via `call_after_refresh` (or the log's `Show`/`Resize` event), and keep routing lines to the deque until the flush has run, so ordering holds for lines arriving in between. The flush must also be correct on first opening, where `write` only queues until the first resize. While shown (and flushed), lines are written directly. Hiding the pane leaves the log as it is.
   Per the customer (Q4) the pane is one continuous stream: nothing clears the log or the buffer, only the `max_lines` / `maxlen` bounds drop old lines. There is no `on_start`.
3. `tests/test_tui.py`: the `Acting.engine` fixture gains an optional `on_line=None` parameter so it accepts the listener. Then new tests with a fake engine that calls `on_line`. Write the open, close, emit, open wrapping test first: it settles the riskiest assumption (the width of a re-shown log at flush time).
4. README: document the key and the pane.

### Assumptions (not questions)

- The existing full-width `#activity` report log is a different thing and stays. The new pane is the "live agent output" pane in the right column, so two logs are on screen. Per the customer (Q1) the pane is the lower half of the detail section: when shown, `#detail` and `#output` have equal height (`1fr` each). When hidden, `#detail` takes the whole column.
- Per the customer (Q1) the pane is closed by default and only `l` opens it. Visibility changes only on `l`; agent start and finish never alter it. State is on the widget, not on disk.
- "Active agent" is the single run in progress (concurrency is out of scope). On start and on finish nothing happens to the pane: output stays and the next run's lines are appended after it (Q2, Q4). Failure is not annotated; the `#activity` log already reports it.
- Because the pane starts hidden, lines streamed while hidden are held in the TUI's buffer and written to the log when the pane is shown, so opening it mid-run shows the run so far. Tests must therefore inspect the log with the pane open (a never-shown `RichLog` has an empty `lines` even when content is queued).
- Runs are not separated or labelled in the pane (Q2, Q4: no added information); the "started" lines in `#activity` tell them apart. A failed run's output is therefore still visible when the next item's agent starts.
- Lines already in the log are not re-wrapped if the terminal is resized. Accepted.
- Lines are written unmodified with `markup=False`, so brackets in agent text are shown literally.
- Nothing guards against late or mis-tagged lines: `engines.run` joins its reader threads before returning and the runner is serial, so neither can occur. Not built, not tested.
- The output log is not focusable (as `#activity`). Tab still alternates between `#items` and `#detail` only. Keyboard scroll-back is out of scope.
- Check steps (`Runner.verify`) stream nothing and are not relevant to this pane (Q3). The hooks fire only from `invoke`, and a check step leaves the pane untouched. With no header there is no idle wording to contradict the tree.

## Acceptance criteria

- A `RichLog #output` sits in the right-hand column below `#detail`, not inside its scroll content, with `auto_scroll` true, `max_lines == 2000`, `markup` false, `wrap` true and `min_width == 1`. It has no header, border title or other status widget. Checked by a test querying the widget.
- At startup `#output` is hidden (`display` false, zero height), its log is empty, and `#detail` fills the right column height.
- Pressing `l` shows the pane; pressing `l` again hides it. The binding is in `Backlog.BINDINGS` with a label naming agent output, so the footer lists it.
- Shown, `#detail` and `#output` have equal height (within one row for rounding) and together fill the right column. Hidden, `#detail`'s height equals the column's. Checked by comparing sizes after toggling.
- Agent start and finish never change the pane's visibility, whether it was shown or hidden beforehand.
- Lines streamed while the pane is hidden are in the log, in order, when it is opened. The test opens the pane before inspecting `lines`.
- Wrapping: with the pane shown at 120x40, a fake engine emits one 200-character line; no strip in the log is wider than the pane's content width, the log has more than one row for it, and the concatenated row text equals the original line (modulo wrap whitespace). Test this twice: line emitted while the pane is shown, and line emitted while it is hidden after having been shown and hidden once (open, close, emit, open). Both give the same strip widths and row count.
- Hidden buffering: open the pane, close it, emit lines, assert the log's `lines` is unchanged, open it, and after layout assert the lines are appended in order. Bound: with the pane hidden after one open, emit 2001 distinct short lines, open; the first is absent and the last 2000 are present (short lines, so `max_lines` wrapped-row counting does not interfere).
- When a run finishes, whether it succeeds, exits non-zero or raises, the log is left as it was: no line, label or title is added or removed. When a check step runs (`Runner.verify`) the log and its visibility are untouched.
- Continuous stream (Q4): `Runner` has no `on_start` attribute and nothing clears the log or buffer. Test: two runs in sequence with different output; with the pane open, the log holds both runs' lines in order, the first run's lines first. Also with the pane hidden during both runs, then opened: both runs' lines, in order.
- `devteam/runner.py` is unchanged by this item (diff check); the TUI sets `runner.on_line` in `on_mount`.
- The TUI receives lines only through `from_agents`. A test calls the TUI's registered `runner.on_line` directly after the app has exited and asserts nothing is raised.
- The `Acting` fixture accepts `on_line` and the two existing agent tests pass; `tests/test_engines.py` passes unchanged.
- The output log is not focusable; the existing focus test (`tests/test_tui.py:143`) passes unchanged and tab still alternates between `#items` and `#detail`.
- A fake engine emitting `[red]x[/red]` produces that literal text in the log; no JSON decoding is added in the TUI or runner.
- `tests/test_tui.py` covers every TUI criterion above with a fake engine emitting lines through `on_line`. The whole suite passes, including the existing `#detail` focus test and `tests/test_engines.py`.
- README mentions the `l` key.

## Depends on

The story "Stream agent output live to log and listener". Already in the repository (`engines.run(..., on_line=...)`, `Runner.on_line`), so nothing blocks this item.

## Out of scope

Streaming output from check steps (a separate story if wanted), search, filtering, log history, keyboard scroll-back, interrupting the agent, concurrency, persisting the toggle across sessions.

## Challenge

Verdict: sound (fifth round). A competent engineer could build this as written and a reviewer could tell whether they had. The three round 4 findings are all acted on in the Analysis and criteria, not only in the response: `on_output` is gone and `devteam/runner.py` is unchanged, the flush is stated to happen after layout with lines routed to the deque until then, and the hidden-buffering criterion names its sequence and has a bound test. Nothing below changes what gets built or how it is judged.

Notes for the implementer, none of them a reason to rework:

1. **The stated reason for buffering while hidden is probably wrong, but the design holds for other reasons.** The Analysis expects a hidden log to report width 0. In Textual 8.2.8 a hidden widget is dropped from the compositor map and sent `Hide`; `_size_updated` and `Resize` go only to widgets still in the map (`screen.py:1352-1380`), so a re-hidden log most likely keeps its last width and a direct write would wrap as before. The buffer is still worth having, for two reasons the item does not give: before the first opening `RichLog.write` queues into `_deferred_renders`, which `max_lines` does not bound (`_rich_log.py:205-213`), and closed-by-default means a never-opened pane would otherwise grow for the whole session; and a line written while hidden would wrap at a stale width if the terminal was resized meanwhile. The item already says the remedy does not depend on the answer, and the criteria test the behaviour, so nothing changes. Like the analyst I could not run the probe (execution was refused), so this is read from the source.

2. **`RichLog` is focusable by default** (`_rich_log.py:47`, `can_focus=True`); `#activity` is only unfocusable because `on_mount` sets it (`tui.py:409`). The criterion "the output log is not focusable" covers it; the implementer has to set it, it does not come for free.

3. **Stale wording.** The last assumption says "The hooks fire only from `invoke`"; there are no hooks left, only `on_line`, which `invoke` passes to the engine (`runner.py:237`). Harmless.
4. **Tests must emit from the agent thread.** `from_agents` swallows the `RuntimeError` that `call_from_thread` raises when called on the app's own thread (`tui.py:585-591`), so a test that calls `runner.on_line` directly while the app is running would drop the line silently and pass or fail for the wrong reason. The criteria already say lines come from a fake engine through `on_line`; keep to that except in the after-exit test.

Checked against the repository as it stands now (STORY-010 to 012 have merged since the last round; the line references still hold): `Runner.on_line` defaults to `None` (`runner.py:161`) and is passed only when set (`:237`); it is set nowhere but `tests/test_engines.py:127`; `active` is set in `invoke` (`:234`) and `verify` (`:268`) and cleared in `finally`; `verify` calls `self.check(self.checkout, log=log)` with no line callback; `engines.run` renders per line, swallows listener errors (`engines.py:61-64`) and joins both readers before returning; `render.py:7` caps lines at 200 characters; `compose` (`tui.py:385-394`) and `BINDINGS` (`:359-368`, three-tuples, `l` free, which keeps `check_action` at `:487` working) are as described; `runner.report` is assigned at `tui.py:408`; the focus assertion is at `tests/test_tui.py:143`; `Acting.engine` (`:214`) takes no `on_line` and the two agent tests that would break are at `:378` and `:418`; Textual is pinned at 8.2.8 and the `min_width` arithmetic matches `_rich_log.py:229-247`.

Customer's decisions: closed by default, opened with `l`, lower half of the detail section (Q1); output stays, nothing added (Q2); check steps not relevant (Q3); one continuous stream (Q4). Each is reflected without embellishment. What the analyst decided alone is confined to the Assumptions and is the sort of thing an analyst may decide: the `l` key, the 2000-line bound, literal brackets, no re-wrap on terminal resize, not focusable, and showing lines that arrived while the pane was closed. The last is the only one a customer might notice; it follows from "toggles it to open when they want to see progress" and from Q4, and the alternative (an empty pane on opening mid-run) would be the surprising one.

Every criterion can fail a test or a diff check, and each traces to the goal, to one of the four answers, or to keeping the existing suite green. The even split on an 80x24 terminal leaves the detail view about 5 lines; the customer was told that in Q1 and chose the half split.

Cheapest way to be wrong: unchanged from last round. Write the open, close, emit, open wrapping test first; it settles the width a re-shown log has at flush time in minutes.

## Challenge response

Findings 4 to 7 are settled in the Analysis and criteria above: `on_line` is kept alongside `on_output`; the `Acting` fixture change is listed; the late-line guard is dropped; the log is not focusable; the shutdown test calls the hooks directly and hook exceptions never alter the run. Finding 3's code claim is accepted and `verify` is now described correctly. Findings 1 to 3 were put to the customer (Questions below) and are answered: pane hidden by default and opened with `l`, lower half of the detail section; output stays after a run ends with nothing added (so the header and the finish hook are dropped); check steps are irrelevant to the pane. The Analysis and criteria above are rewritten to match.

## Challenge response (round 2)

1. Wrapping: confirmed against Textual 8.2.8. The widget is now `min_width=1` and a criterion checks a 200-character line at 120x40 with strip widths and full text.
2. Hidden writes: the TUI buffers lines while the pane is hidden and writes them on show, so the hidden-after-shown width problem cannot arise. A criterion covers open, close, emit, open. Tests inspect the log with the pane open. Not probed by running code (execution was refused here); the criterion is the check.
3. Clearing: conceded, it was my assumption. Asked as Q4; clearing criteria are conditional on the answer, with a recommendation to drop `on_start`.
4. Output-hook exceptions: the runner test now uses a fake engine with no try/except so the runner's wrapper is what is tested.

## Challenge response (round 3)

Q4 is answered: continuous stream. `on_start`, the clear-on-start behaviour and the conditional criteria are removed; the criteria now state the continuous-stream behaviour and a two-run test. No open questions remain.

## Challenge response (round 4)

1. Accepted. `on_output` is dropped: the TUI sets the existing `Runner.on_line` through `from_agents`, `runner.py` is unchanged, and the three runner criteria are deleted. The `Acting` fixture change stays.
2. Accepted. The flush on show must happen after layout (`call_after_refresh` or `Show`/`Resize`), with lines kept in the deque until it has run.
3. Accepted. The hidden-buffering criterion now states the open, close, emit, open sequence and a 2001-line bound test.

## Questions

1. When should the output pane be shown? (a) Always visible when the TUI opens until toggled with `l`, even while agents are stopped; (b) appears when an agent starts and collapses when idle, unless toggled off; (c) hidden until `l` is pressed. Should it take an even split of the right column with the detail view, or a smaller fixed height (say 6 rows)? On an 80x24 terminal an even split leaves the detail view about 5 usable lines.

   **Answer:** Output pane is closed by default. User toggles it to open when they want to see progress. It should take up the lower half of the detail section.
2. When an agent finishes or fails, should its last output stay on screen, labelled as finished or failed, until the next agent starts (recommended, so the customer can see what it was doing when it failed), or should the pane clear at once?

   **Answer:** The output should stay on the screen. It should not have any additional information added, it is just a stream from the agent.
3. The project check step (running the test suite) shows "running" in the tree but streams no output. Should the pane (a) stay idle for check steps, with header wording that does not claim nothing is running, or (b) show a header naming the check while it runs, with no lines streamed? Streaming check output would be a separate story.

   **Answer:** The output pane is just what is coming out of agent interactions so the check step is not relevant.
4. When the next agent starts, should the pane be emptied first, or should output simply keep scrolling as one continuous stream (like `tail -f`, bounded to the last 2000 lines, with runs told apart by the "started" lines in the activity log)? Emptying means that when one agent fails and another item is pending, the failed run's output disappears as soon as the next agent starts, usually within seconds. My recommendation is a continuous stream: it is simpler and keeps failure output on screen.

   **Answer:** It should keep the existing output, just adding the output from the next agent to what is already there

## Implementation

Implemented the live output pane in `devteam/tui.py`. A right-hand `Vertical #right` contains the existing `#detail` and sibling `RichLog #output`. The output starts hidden; `l` toggles it, with an "Agent output" footer binding. When open the two panes divide the column equally. The log has `auto_scroll=True`, `max_lines=2000`, `markup=False`, `wrap=True`, `min_width=1`, no title or status, and cannot receive focus.

`on_mount` registers the existing `runner.on_line` through `from_agents`. Hidden output goes into a bounded `deque(maxlen=2000)`. Opening schedules a flush with `call_after_refresh`, keeping arriving lines buffered until layout and the ordered flush complete. Output stays across runs and toggles; no start, finish or check behavior was added. `devteam/runner.py` and `tests/test_engines.py` are unchanged. Updated the `Acting` fixture to accept `on_line` and documented `l` in README.

Added two focused tests using a real Runner and a fake engine on a worker thread: live versus hidden-after-shown wrapping of a 200-character line; ordered, bounded hidden buffering across runs. These also exercise first opening, literal brackets, pane geometry and callback delivery after shutdown. Geometry uses outer `region.height`: Textual's `size.height` excludes the existing detail border, so comparing content sizes would incorrectly report a two-row gap. The comprehensive acceptance automation and full suite remain for the tester, as directed by the implementation instructions.

Checks and actual results:

- Initial `uv run python -m unittest tests.test_tui.AgentOutput`, before implementation (exit 1):

  ```text
  textual.css.query.NoMatches: No nodes match '#output' on Screen(id='_default')
  Ran 2 tests in 0.253s
  FAILED (errors=2)
  ```

- First run after implementation (exit 1) found two test setup/assertion mistakes: the new story lacked its required parent, and the layout assertion compared content heights rather than occupied heights. Corrected both in the focused tests:

  ```text
  devteam.backlog.InvalidRecord: story requires a parent
  AssertionError: 30 != 28
  Ran 2 tests in 0.273s
  FAILED (failures=1, errors=1)
  ```

- Corrected `uv run python -m unittest tests.test_tui.AgentOutput` (exit 0):

  ```text
  ..
  ----------------------------------------------------------------------
  Ran 2 tests in 3.303s

  OK
  ```

  Also emitted an asyncio slow-task diagnostic for the screen message pump (`took 0.188 seconds`).

- `uv run python -m unittest tests.test_tui tests.test_engines` (exit 0), including the unchanged focus test and existing agent tests:

  ```text
  ----------------------------------------------------------------------
  Ran 27 tests in 38.172s

  OK
  ```

  Also emitted asyncio slow-task diagnostics: Actions message pumps took 0.128 and 0.139 seconds; screen update took 0.112 seconds; screen message pump took 0.198 seconds; FooterKey message pump took 0.123 seconds. No test failures.

- `git diff --check`: exit 0, no output.
- `git diff --exit-code -- devteam/runner.py`: exit 0, no output.
- `git branch --show-current`: `devteam/STORY-009`. Changes left in the working tree; no commit made.

No implementation blockers.

## Tests

All in `tests/test_tui.py`, class `AgentOutput`, driving the real `Backlog` app (Textual pilot, 120x40) with a real `Runner` and a fake engine that emits lines through `on_line` from a worker thread. Run one with `uv run python -m devteam check tests.test_tui.AgentOutput.<test>`, or the class with `tests.test_tui.AgentOutput`.

- Widget properties, no header/title, sits below `#detail` outside its scroll content: `test_output_pane_is_a_plain_log_below_detail_outside_its_scroll_content`
- Hidden at startup, empty, `#detail` fills the column; geometry once toggled; `l` binding labelled for agent output: `test_l_toggles_the_pane_and_the_footer_names_it` and the start of `test_wrapping_after_open_close_emit_open_matches_live_output`
- Start/finish never change visibility (success, non-zero exit, raising engine): `test_runs_never_change_visibility_whether_they_succeed_or_exit_non_zero`, `test_a_run_that_raises_leaves_the_log_and_visibility_as_they_were`
- Hidden lines present and ordered on opening; 2001-line bound: `test_hidden_buffer_is_bounded_and_preserves_order_across_runs`
- Wrapping of a 200-character line, live and open/close/emit/open: `test_wrapping_after_open_close_emit_open_matches_live_output`
- Check step leaves log and visibility alone: `test_a_check_step_leaves_the_pane_untouched`
- Continuous stream, shown or hidden; no `on_start`; listener registered on mount: `test_two_runs_form_one_continuous_stream_whether_the_pane_is_shown_or_hidden`, `test_runner_has_no_start_hook_and_the_tui_registers_its_listener_on_mount`
- Listener safe after the app has exited: end of `test_wrapping_after_open_close_emit_open_matches_live_output`
- Not focusable, tab alternates items/detail: `test_output_log_is_not_focusable_and_tab_alternates_items_and_detail`; existing focus test and the `Acting` agent tests still pass
- Literal brackets: `test_brackets_in_agent_text_are_shown_literally`
- README mentions `l`: `test_readme_mentions_the_l_key`
- `devteam/runner.py` unchanged: confirmed by `git diff main -- devteam/runner.py` (empty); no test, as it is a property of the diff.

Whole suite: 152 tests pass.

## Test run

Run by the harness, 2026-10-07 15:37 UTC. Full output: `/home/tarttelin/projects/pyruby/dev-team/backlog/log/STORY-009/verify-20261007T153542769249.log`

Passed: `the project check`

```text
uv run python -m unittest discover -s tests
......................................................................................................................Executing <Task pending name='message pump Actions()' coro=<MessagePump._process_messages() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/message_pump.py:571> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.133 seconds
.Executing <Task pending name='message pump Actions()' coro=<MessagePump._process_messages() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/message_pump.py:571> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.134 seconds
...Executing <Task pending name="message pump Screen(id='_default')" coro=<MessagePump._process_messages() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/message_pump.py:571> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.130 seconds
..Executing <Task pending name="message pump Screen(id='_default')" coro=<MessagePump._process_messages() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/message_pump.py:571> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.213 seconds
.Executing <Task pending name="message pump Screen(id='_default')" coro=<MessagePump._process_messages() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/message_pump.py:571> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.106 seconds
......Executing <Task pending name="message pump Screen(id='_default')" coro=<MessagePump._process_messages() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/message_pump.py:571> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.153 seconds
.....................
----------------------------------------------------------------------
Ran 152 tests in 90.163s

OK
```

## Review

Verdict: approve. I found no defect that breaks a criterion. The harness run passed all 152 tests.

### Findings (minor, none blocking)

1. Resizing the terminal while the pane is shown does not re-wrap lines already written. The item accepts this explicitly, so it is not a defect.
2. `test_runner_has_no_start_hook_and_the_tui_registers_its_listener_on_mount` only asserts that `on_line` is non-None after mount. It does not prove that the listener goes through `from_agents`. The after-exit call at the end of the wrapping test covers that path, since an unguarded call would raise.
3. The flush race is handled correctly. Show then hide before the flush runs is a no-op, because `flush_output` checks `display`. Show, hide, show leaves a harmless second flush. Arrivals during the wait go to the deque, and flush and writes both run on the app thread, so order holds.

### Criteria satisfied

- **Widget and properties:** `compose` in `devteam/tui.py` puts `RichLog #output` (auto_scroll, max_lines=2000, markup=False, wrap=True, min_width=1) as a sibling of `#detail` in `Vertical #right`. Test: `test_output_pane_is_a_plain_log_below_detail_outside_its_scroll_content`.
- **Hidden at startup:** `display = False`. The wrapping test asserts zero height, empty `lines` and `#detail` height equal to the column's.
- **`l` toggles:** the binding `("l", "toggle_output", "Agent output")` is in `BINDINGS`, and `test_l_toggles_the_pane_and_the_footer_names_it` covers it.
- **Equal heights:** both `1fr`. The test compares outer `region.height`, within 1 row, and checks that the two sum to the column height. When hidden, `#detail` equals the column.
- **Visibility unchanged by runs:** nothing in a run touches `display`. Covered for ok, non-zero exit and raising runs, shown and hidden.
- **Hidden lines present and ordered on open:** `test_hidden_buffer_is_bounded_and_preserves_order_across_runs` asserts order on open and the 2001-line bound (first absent, last 2000 present).
- **Wrapping:** the 200-character line is tested live and with open, close, emit, open. Both give the same strip widths, strip width within content width, more than one row, and rejoined text equal to the original.
- **Hidden buffering:** the log's `lines` are unchanged while hidden, and the lines append after layout via `call_after_refresh`.
- **Run finish and check step:** the log is untouched (the check-step and raising tests).
- **Continuous stream:** there is no `on_start`, and nothing clears the log or buffer. Both the shown and the hidden two-run tests pass.
- **runner.py unchanged:** the diff touches only README, `tui.py` and `tests/test_tui.py`. `on_line` is set in `on_mount` through `from_agents`.
- **Safe after exit:** `runner.on_line("after shutdown")` is called after the app has exited and raises nothing.
- **Fixture and engines:** `Acting.engine` accepts `on_line`, and `tests/test_engines.py` is untouched.
- **Not focusable:** `can_focus = False` is set on the log, and the focus test and tab alternation pass.
- **Literal brackets:** `[red]x[/red]` appears literally, and no JSON decoding was added.
- **README:** it mentions `l`, and a test checks that.
