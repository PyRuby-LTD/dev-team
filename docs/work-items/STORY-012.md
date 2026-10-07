---
id: STORY-012
type: story
title: Return a rejected PR's comments to implement
parent: EPIC-003
workflow: default
step: publish
---
As the customer, I want a rejected PR's review comments passed back to implement, so that the implementer can address them without `gh` access.

## Original acceptance criteria (superseded by "Acceptance criteria (current)" below)

- Moving to `rejected` reads every review body, inline review comment and conversation comment on the PR with `gh`.
- They are written under a `## Pull request feedback` heading in the item, replacing any earlier such section, and the item moves to `implement`.
- `prompts/implement.md` tells the implementer to address that section.
- If the `gh` call fails, the item stays at `rejected` and the error is shown.

## Analysis

### What exists today

- STORY-010 has landed on this branch. `workflows/default.json` has `pull-request` (human) -> `rejected` (owner `harness:rejected`, transition `completed` -> `implement`). `devteam/runner.py` has `HARNESS_ACTIONS` mapping `rejected` to a placeholder `rejected(runner, record)` that returns `"completed"`. The runner then applies the transition. Nothing touches `gh` or the PR yet.
- `Runner.run_item()` already turns `StepFailed`, `git.GitError`, `InvalidRecord` and `OSError` (which covers `gh` not being installed) into: item left at its step, `FAILED - <reason>; still at rejected` reported, no retry until `retry()` or restart. That is the "stays at `rejected` and the error is shown" behaviour; the new action only has to raise on failure and write nothing before it has everything.
- `devteam/questions.py` has `replace_section(body, heading, content)`, which replaces or appends a level-two section. `Runner.verify` uses it for `## Test run`, and is the pattern to follow (`repository.write_body(...)`).
- The publisher records the PR URL under a `## Pull request` heading in the item body (`prompts/publish.md`). That is free text written by an agent, and is the only record of which PR belongs to the item.
- `prompts/implement.md` mentions `## Review` and `## Tests` but not PR feedback. The generic protocol only mentions `## Feedback`.
- The customer's note given when moving to `rejected` is saved under `## Feedback` by `Repository.transition`, before the harness runs. That is separate from this story and must survive it.
- No `gh` stub exists in `tests/stubs/` (only `claude` and `codex`). `gh` is installed on this machine, but tests must not depend on it or the network.

### What would change

1. `devteam/runner.py`: the `rejected` action:
   1. Find the PR URL in the item's `## Pull request` section. If the section or a `https://github.com/<owner>/<repo>/pull/<n>` URL is missing, raise `StepFailed` saying so. If the section holds several such URLs, the last one is used (a rejected PR may have been closed and a new one opened, and the publisher may append rather than replace). Changing `prompts/publish.md` is out of scope.
   2. Read all three comment kinds with `gh api <endpoint> --paginate`, parsing stdout with a `raw_decode` loop. Fields used, per endpoint (confirmed against the customer's real output for PR 2, see Questions; each endpoint returned a single JSON array): reviews `pulls/<n>/reviews`: `user.login`, `state`, `body`, `submitted_at`; inline comments `pulls/<n>/comments`: `user.login`, `path`, `line`, `original_line`, `subject_type`, `created_at`, `body`; conversation comments `issues/<n>/comments`: `user.login`, `created_at`, `body`. Reviews have no `created_at`; the date shown for a review is `submitted_at`. A missing or null `user` is rendered as `unknown author`. Any non-zero exit, timeout, non-JSON output, or JSON that is not an array of objects raises `StepFailed` naming the call (quoting gh's stderr where there is one), before anything is written. Nothing else may escape as `KeyError`, `TypeError` or `ValueError`, since `run_item` does not catch those.
   3. Render to Markdown, splitting every body with `str.splitlines()` (the same splitting `replace_section` and `questions.parse` use, so a lone `\r` or similar cannot smuggle a heading past the blockquote), blockquote every line, and write with `questions.replace_section(body, "Pull request feedback", ...)` via `repository.write_body`. Return `"completed"`.
2. `prompts/implement.md`: one paragraph telling the implementer to address every comment under `## Pull request feedback` if present, alongside the existing `## Review` and `## Tests` guidance.
3. `tests/stubs/gh`: a stub that serves canned JSON by endpoint and can be told to fail, plus a test module driven like `tests/test_pr_decision.py`.
4. `README.md`: the harness-owned `rejected` step reads the PR comments and needs `gh` authenticated.

### Assumptions (stated, not questions)

- The PR is identified by the URL under `## Pull request`, not by branch name lookup. Owner, repo and number are parsed from that URL, and `gh api` is used so that pagination is explicit.
- "Every" means every comment, including those from bots, resolved threads and outdated diffs. Nothing is filtered by author or state. The one exception is a review with an empty body (a bare approval or the shell around inline comments): its inline comments are listed, but no empty body entry is written.
- Each entry names its kind, author and, for inline comments, the file and line, so the implementer can locate it. Ordering within each kind is as returned by GitHub (oldest first).
- If the PR has no comments at all, the section is still written, saying there were none, and the item moves to `implement`. An empty rejection is the customer's call; the harness does not second-guess it.
- A second rejection replaces the section with the full current comment set (not only the new comments). Comments already addressed will reappear; that is accepted for "replacing any earlier such section".
- Only submitted reviews are acted on (customer's feedback, superseding their answer to Question 2). A review whose `state` is `PENDING`, or that has no `submitted_at`, is skipped entirely: no entry, no error, no extra `gh` call. Any inline comment that `pulls/<n>/comments` happens to return is treated like any other; there is no attempt to read a pending review's own comments (`pulls/<n>/reviews/<id>/comments`). Handling pending reviews is explicitly out of scope for now. This closes the earlier Questions 2 and 3.
- The customer's real `gh` output was provided in untracked root files and has since been deleted by the customer; it is not in the repository or its history, so there is no real fixture to reuse. I read it earlier: reviews carry `submitted_at` and no `created_at`; the inline comment had `path` `workflows/default.json`, `line` 16, `original_line` 16, `subject_type` `line`; there were two `COMMENTED` reviews (one with an empty body), one inline comment and one conversation comment; each endpoint printed a single JSON array. The field list above stands on that. The fixtures are therefore written by the implementer to that shape and labelled as modelled on real `gh` output, not captured from it.
- Fixture location: `tests/fixtures/gh/` (tracked, alongside the existing `tests/fixtures/streams/`), committed as part of the implementation. This closes the earlier Question 4; the checkout stays clean because nothing untracked is left in the repository root.
- The section is written only after every `gh` call succeeded, so a failure leaves the body unchanged and the item at `rejected`. After the customer fixes the cause, retry is the existing mechanism (`t` in the TUI, or restart). No new retry control is in scope.
- The action needs neither the checkout nor a counted run, as with the placeholder.
- The failed report line ends with a log pointer, though no log exists for a harness action. That is existing STORY-010 behaviour and out of scope here.

### Risk

- `gh` authentication or network trouble is the expected failure, and the message comes from `gh` itself.
- The agent-written `## Pull request` section may not contain a plain URL (for instance if publish produced prose). That fails with a clear message rather than guessing. The criteria below pin the URL form.

## Acceptance criteria (current)

This is the authoritative list; it replaces the original one above. Each criterion is checkable by a test run through `devteam run`/`backlog move` with a stub `gh` on `PATH`, or by reading the diff.

### Revisions after the challenge

- **Rendering (finding 1).** Every line of every comment body is written blockquoted (`> ` prefix, including blank lines), so no comment line can begin a `#`/`##` heading, a fence or a `## Feedback`/`## Questions`/`## Pull request` marker. Each entry is introduced by a bold line (not a heading), e.g. `**Inline comment** by alice on src/a.py line 12 (2026-03-01):`. Confirmed by reading `replace_section`: a section ends at the next level-one or level-two heading regardless of code fences, so the blockquote is needed.
- **Pagination (finding 2).** I could not run `gh` in this session (not permitted), so the output shape is not verified against the installed version. The design therefore does not depend on it: call `gh api --paginate` (no `--slurp`, no `--jq`) and parse stdout with `json.JSONDecoder.raw_decode` in a loop, flattening each array found. That accepts both a single array and the concatenated `[...][...]` that `--paginate` prints for array endpoints. A stub emitting one array and a stub emitting two concatenated arrays must both work. The implementer cannot run `gh` (no `gh` access is the premise of the story), so the field names and `PENDING` behaviour are settled by the customer's pasted output (Questions 1 and 2).
- **Repeat rejections (finding 3).** No customer question: the full set is written, each entry carries its created date, and the implement prompt says the section is the whole history of the PR, that comments the code already meets need no change, and that the latest `## Feedback` note takes precedence. This also keeps the customer's "every" and "replacing" wording intact.
- **Outdated and file-level comments (finding 4).** Line is `line`, else `original_line` marked `(outdated)`, else omitted (file only) for comments with `subject_type` of `file` or no line at all. A `null` is never printed.
- **Unsubmitted review (finding 5).** Superseded by the customer's answer to Question 2: a `PENDING` review does not fail the step; its comments are included (see the assumptions and criterion 10).
- **Host, timeout (finding 6).** The PR URL must be `https://github.com/<owner>/<repo>/pull/<n>`; other hosts fail as a missing URL. A timeout of 60 seconds per `gh` call raises `StepFailed` naming the call. A missing `gh` surfaces as the `OSError` text, and the test asserts the output contains `gh`.

### Criteria

1. With the item at `pull-request` and a `## Pull request` section containing a `https://github.com/<owner>/<repo>/pull/<n>` URL, `devteam backlog move <id> rejected` followed by a run pass leaves the item at `implement`. The report line reads `rejected (harness: rejected): completed -> implement`.
2. The stub `gh` records its argv. Three calls are made, each exactly `gh api repos/<owner>/<repo>/pulls/<n>/reviews`, `.../pulls/<n>/comments` and `.../issues/<n>/comments` followed by `--paginate`, with owner, repo and number taken from the URL. No `--slurp` or `--jq`.
3. The item body then has a `## Pull request feedback` heading. Under it appears the text of every non-empty review body, every inline comment and every conversation comment from the stub, each with its author and date (the submitted date for reviews, the created date otherwise), reviews also with their state. A null or missing author renders as `unknown author`. The stub data uses exactly the field names listed under "What would change". Inline comments give file and line. The stub data has at least one of each kind, a second page for one endpoint (as concatenated arrays), one outdated inline comment (`line: null`, `original_line` set), one file-level comment, and a review with an empty body (its inline comments appear, no empty entry for it). The output never contains `None` or `null`.
4. Given an item that already has a `## Pull request feedback` section with different text, after the action the old text is gone and exactly one such heading exists. Other sections (`## Feedback`, `## Pull request`, `## Implementation`) are unchanged byte for byte.
5. A note given with `move ... rejected -m "..."` is still present under the single real `## Feedback` heading afterwards.
6. Hostile text: with stub comment bodies containing a `## Feedback` line, a `# comment` line inside a code fence, a `## Pull request feedback` line, and a line `text\r## Feedback` (lone carriage return, not `\r\n`), two successive rejections (the second with different stub comments) leave exactly one `## Pull request feedback` heading, none of the first round's text, the `-m` note under the real `## Feedback`, and `devteam/questions.py` parsing finds no questions from comment text.
7. If the stub `gh` exits non-zero for any of the three calls (tested separately), the item stays at `rejected`, the body is unchanged byte for byte, and the output contains `FAILED` and gh's stderr text. The run pass does not retry it in the same session.
8. If `gh` is not on `PATH`, the same outcome as criterion 7, and the output contains `gh`.
9. If a `gh` call exceeds the timeout (the timeout is a module constant a test can lower, stub sleeps), the same outcome as criterion 7 with the output naming the timeout.
10. If `reviews` returns a `PENDING` review (state `PENDING`, with a non-empty body, and `submitted_at` null or absent), the item still moves to `implement`, the feedback section contains nothing from that review (its body text is absent), and the stub records exactly the three calls of criterion 2. Submitted reviews alongside it are still rendered. The output never contains `None` or `null`.
10c. If the `## Pull request` section holds two matching URLs (different numbers), the stub records calls for the last one only, and no call for the first.
10a. If the stub `gh` exits 0 and prints (a) text that is not JSON, or (b) a JSON object rather than an array, for any of the three calls, the outcome is as criterion 7 (item stays at `rejected`, body unchanged, output contains `FAILED` and names the call). No traceback escapes the run pass.
10b. A comment whose `user` is null renders as `unknown author`, and the output never contains `None` or `null`.
11. If the item has no `## Pull request` section, or it holds no github.com PR URL, the step fails as in criterion 7 with a message saying the PR URL is missing, and the stub records no `gh` call.
12. A PR with no comments produces a `## Pull request feedback` section that states there are none, and the item moves to `implement`.
13. `prompts/implement.md` names `## Pull request feedback` exactly, and says the section holds the whole history of the PR with dates, that comments the code already meets need no further change, and that the latest `## Feedback` note takes precedence. A test asserts the rendered implement prompt contains the heading.
14. `HARNESS_ACTIONS` keys in `devteam/runner.py` are still exactly `merged` and `rejected`, `workflows/default.json` is unchanged, and `merged` is not modified. The existing suite (`uv run python -m devteam check`) passes.
15. The tests use only the stub `gh` under `tests/stubs/`; none calls the real `gh` or the network. The stub's canned JSON lives in tracked files under `tests/fixtures/gh/`, one per endpoint, with the field names listed under "What would change". A baseline set (two `COMMENTED` reviews one with an empty body, an inline comment on `workflows/default.json` line 16, one conversation comment) has a test asserting both review states, the file and line, and the conversation comment appear, with the empty-body review producing no entry. Synthetic cases (second page, outdated, file-level, null user, pending review, hostile text) are separate fixtures or inline data. Baseline fixtures are described in a comment as modelled on real `gh` output, not captured. After the work, `git status --porcelain` in the repository root is empty apart from intended changes (no stray `gh_api_*` files).
16. `README.md` states that the `rejected` step reads the PR's comments with `gh`, needs it authenticated, and on failure leaves the item at `rejected`.

## Questions

1. Neither the analyst, the challenger nor the implementer can run `gh`, so the JSON field names (notably that reviews carry `submitted_at` and no `created_at`) and the `--paginate` output shape rest on recollection. Please run these once against a PR that has at least one review, one inline comment and one conversation comment, and paste the output (trimmed if long) under your answer: `gh api repos/<owner>/<repo>/pulls/<n>/reviews --paginate`, `gh api repos/<owner>/<repo>/pulls/<n>/comments --paginate`, `gh api repos/<owner>/<repo>/issues/<n>/comments --paginate`. It becomes the stub's fixture. If you would rather not, say so and we will accept the first real rejection as the test.

   **Answer:** See gh_api_10_<call>.txt files in the root
2. If a `PENDING` (unsubmitted) review turns up when the PR is read, should the step fail telling you to submit your review first, as currently drafted in criterion 10? Or should it be treated like any other review?

   **Answer:** Act on the PENDING review comments

3. A pending (unsubmitted) review's inline comments may not be returned by `gh api repos/<owner>/<repo>/pulls/<n>/comments`; if so, your answer to Question 2 needs a fourth call per pending review, and none of us can run `gh` to check. Please start a review on any PR with one inline comment, do not submit it, run `gh api repos/<owner>/<repo>/pulls/<n>/reviews --paginate`, `gh api repos/<owner>/<repo>/pulls/<n>/comments --paginate` and, with the review's `id` from the first, `gh api repos/<owner>/<repo>/pulls/<n>/reviews/<id>/comments --paginate`, and put the three outputs in tracked files (see Question 4). If you would rather not, choose instead: (a) read pending comments through the fourth call, building it from the documented API and accepting that the pending fixture is synthetic; or (b) have the section say plainly that an unsubmitted review exists and its comments were not read.

   **Answer:** Withdrawn: per the customer's later feedback, pending reviews are ignored.

4. Where should the real `gh` output live so the checkout is clean when the item is played? Our suggestion: commit the three per-endpoint `gh_api_10_*` files to `main` under `tests/fixtures/` (and delete or commit `gh_api_10.txt` there too), along with the Question 3 outputs if you supply them. The alternative is the backlog directory.

   **Answer:** Withdrawn: the customer deleted the files; fixtures are written under `tests/fixtures/gh/` by the implementer.

Questions 1 and 2 are answered and folded into the analysis and criteria above. Questions 3 and 4 are closed by the customer's feedback (pending reviews are ignored; the root files were deleted, fixtures go in `tests/fixtures/gh/`). Challenge findings: 1 (pending comments) is resolved by ignoring pending reviews, criterion 10; 2 (untracked fixtures) by criterion 15; 3 (several URLs) by criterion 10c; 4 by the assumptions. No questions remain.

## Challenge

Verdict: sound (fourth round). A competent engineer could build this from criteria 1 to 16, and a reviewer could fail any of them from a test run or the diff. The third round's findings are closed: pending reviews are skipped per the customer's last feedback (criterion 10), fixtures are tracked under `tests/fixtures/gh/` (criterion 15), and the last URL wins (criterion 10c). Claims about the code were rechecked against this branch and hold: `rejected` is a placeholder in `HARNESS_ACTIONS` returning `"completed"`; `run_item` catches `StepFailed`, `git.GitError`, `InvalidRecord`, `InvalidWorkflow` and `OSError` and reports `FAILED - ...; still at rejected, not retried until restart`; `replace_section` ends a section at any line matching `#{1,2}\s` regardless of fences and splits with `splitlines()`; `Repository.transition` writes the `-m` note under `## Feedback` before the harness action runs; `prompts/implement.md` names only `## Review` and `## Tests`; `prompts/publish.md` only says to record the URL under `## Pull request`; `tests/stubs/` holds `claude` and `codex` only; the repository root has no `gh_api_*` files and the checkout is clean. Scope traces to the customer's four original points, their answer to Question 1 and their last feedback.

Notes for the implementer and reviewer follow. None changes what is built.

1. **Stale text contradicts criterion 10; criterion 10 governs.** Under "Revisions after the challenge", the "Unsubmitted review (finding 5)" bullet still says a `PENDING` review's "comments are included", and the "Pagination" bullet says the `PENDING` behaviour is settled by the customer's pasted output. Question 2's answer ("Act on the PENDING review comments") also still stands in the text. All three are superseded by the customer's last feedback ("only act on submitted reviews and ignore anything else"), which the assumptions and criterion 10 state correctly: a `PENDING` review produces no entry, no error and no fourth call.

2. **The field names can no longer be checked against real output.** The customer's files are deleted and no role here can run `gh`. The list rests on two independent readings made while the files existed (the analyst's, and the previous challenge round with `jq`), which agree, and criterion 15 has the fixtures labelled as modelled, not captured. That is an honest footing. The cheapest way to be wrong is still a renamed or absent field, and the first real rejection settles it. Because criterion 10a and the "nothing escapes as `KeyError`" rule apply, the worst case is a missing date or `unknown author`, not a crash or a lost comment.

3. **Criterion 8 needs a constructed `PATH`.** The helpers in `tests/test_pr_decision.py` prepend the stub directory to the real `PATH`, and the real `gh` is installed on this machine, so simply omitting the stub would call the real `gh` and break criterion 15. The test has to build a `PATH` that has `git` and Python but no `gh`. "The output contains `gh`" is also weak, since a temporary directory or test name could contain those letters; assert on the `OSError` text naming `'gh'` instead.

4. **Criterion 1's report line carries the item id.** The runner prints `<id> rejected (harness: rejected): completed -> implement`; read "reads" as "contains".

5. **Analyst's choices, not the customer's, and cheap to change.** The 60 second timeout, the `unknown author` wording, the bold entry lines, and treating an inline comment that `pulls/<n>/comments` returns for a pending review like any other. The last is slightly wider than "ignore anything else", but as far as I know the API does not return a pending review's comments from that endpoint, so it should not arise. That is from memory of the API, not verified.

## Feedback

- **answered -> analysis:** I've removed the additional files now you've seen them. For PENDING reviews, I don't want to tackle this right now so let's pretend you only act on submitted reviews and ignore anything else.

## Implementation

Implemented the rejected harness action: use the last GitHub PR URL under `## Pull request`, read the three comment endpoints with `gh api <endpoint> --paginate` and a 60-second timeout, and parse consecutive JSON arrays. Invalid output, failed calls and timeouts fail before writing anything. Submitted non-empty review bodies, inline comments and conversation comments are rendered with authors, dates, review states and file/line locations. Pending and undated reviews are skipped. Comment bodies are blockquoted using `splitlines()`, including blank lines and lone carriage returns. The full feedback section replaces its previous contents before the existing transition returns the item to implementation.

Updated the implement prompt with the whole-history and latest-customer-note guidance, and documented authentication and failure behavior in README. Added an offline gh stub, baseline fixtures modelled on the customer's real output (not captured), and focused tests for pagination, rendering, hostile text, replacement, URL selection, missing gh, timeouts and invalid responses. Updated the existing harness and PR-decision fixtures for the now-required URL and comment retrieval. The merged action, harness registry keys and default workflow are unchanged. No real gh or network calls were made.

Checks and actual output:

- Initial direct run: `uv run python -m unittest tests.test_pr_feedback tests.test_runner tests.test_pr_decision` exited 1. The existing retry test's final success path lacked a PR URL; updated its fixture and supplied empty comments for that harness plumbing test.

```text
FAIL: test_failure_waits_for_retry_or_restart (tests.test_runner.HarnessSteps.test_failure_waits_for_retry_or_restart)
Traceback (most recent call last):
  File "/home/tarttelin/projects/pyruby/dev-team/tests/test_runner.py", line 218, in test_failure_waits_for_retry_or_restart
    self.assertEqual("implement", self.repo.scan().valid[self.story.id].metadata["step"])
AssertionError: 'implement' != 'rejected'
- implement
+ rejected

Ran 34 tests in 10.299s

FAILED (failures=1)
```

- Rerun of the same direct command exited 0:

```text
..................................
----------------------------------------------------------------------
Ran 34 tests in 10.269s

OK
```

- Project check: `uv run python -m devteam check tests.test_pr_feedback` exited 0:

```text
uv run python -m unittest tests.test_pr_feedback
.......
----------------------------------------------------------------------
Ran 7 tests in 1.585s

OK

check passed; full output: /home/tarttelin/projects/pyruby/dev-team/backlog/log/check/20261007T143647395992.log
```

- `git diff --check` exited 0 with no output. Root status contains only the intended source, documentation, test and fixture changes; no stray gh output files. The full suite is left for the tester's step as instructed. No known implementation blockers remain.

## Tests

Run one test: `uv run python -m devteam check tests.test_pr_feedback.<Class>.<test>`; the whole module: `uv run python -m devteam check tests.test_pr_feedback`. All use the stub `tests/stubs/gh` and the fixtures in `tests/fixtures/gh/`; no real `gh` or network.

Command-line tests (`RejectedThroughTheCommandLine`, driving `devteam backlog move` and `devteam run --once` as subprocesses):

- Criteria 1, 2, 3 (baseline, empty-body review gets no entry), 5, 15 baseline: `test_rejection_returns_the_pr_comments_to_implement_and_keeps_the_note`.
- Criteria 7 (gh non-zero, stderr shown, body unchanged): `test_rejection_with_gh_failing_leaves_the_item_at_rejected`.
- Criterion 8 (no gh on PATH): `test_rejection_without_gh_on_the_path_leaves_the_item_at_rejected`.
- Criterion 11 (no PR URL, no gh call): `test_rejection_without_a_pr_url_makes_no_gh_call`.
- Criterion 12: `test_rejection_of_a_pr_without_comments_says_so`.

Runner-level tests (`PullRequestFeedback`, written by the implementer, driving the runner in-process against the stub):

- Criteria 2, 4, 10c, 15: `test_baseline_and_last_url`.
- Criteria 3, 10, 10b (concatenated pages, outdated, file-level, null user, pending review): `test_pagination_pending_and_inline_locations`.
- Criteria 4, 6 (hostile text, repeat rejection): `test_hostile_comments_and_repeat_replacement`.
- Criteria 7, 10a (each endpoint failing or returning invalid JSON): `test_endpoint_failures_and_invalid_pages`.
- Criteria 8, 9 (timeout, missing gh): `test_timeout_and_missing_executable`.
- Criterion 11: `test_missing_url_never_calls_gh`.
- Criteria 12, 13 (implement prompt names the heading): `test_empty_feedback_and_prompt`.

Criterion 14 is covered by `tests.test_pr_decision.DefaultWorkflowShape`, `tests.test_runner.HarnessSteps` and the whole suite (140 tests passing). Criteria 13 and 16 wording (prompt and README text) is otherwise checked by reading the diff.

## Test run

Run by the harness, 2026-10-07 14:41 UTC. Full output: `/home/tarttelin/projects/pyruby/dev-team/backlog/log/STORY-012/verify-20261007T144012749391.log`

Passed: `the project check`

```text
uv run python -m unittest discover -s tests
......................................................................................................................Executing <Task pending name='message pump Actions()' coro=<MessagePump._process_messages() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/message_pump.py:571> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.125 seconds
......................
----------------------------------------------------------------------
Ran 140 tests in 76.532s

OK
```

## Review

Verdict: approve. No finding blocks acceptance. Two small evidence gaps and one cosmetic edge, most significant first.

Findings:

1. Criterion 10 is only partly pinned by its own test. `test_pagination_pending_and_inline_locations` does not assert that the item reached `implement` or that exactly three `gh` calls were recorded. Both are covered elsewhere (`test_baseline_and_last_url` asserts the three calls and the move). The code has no fourth-call path, so the risk is low. Fix: add those two assertions to the pending test.
2. A review whose body is whitespace only is truthy, so it gets an entry with a blank quoted line. Trigger: `"body": "  "`. The result is a harmless empty-looking entry. Fix: test `body.strip()`.
3. A comment with an empty body renders an introduction line ending in `:` with no quoted text. This is cosmetic and arguably correct for "every comment".

Criteria found satisfied, with evidence:

- 1, 5: `RejectedThroughTheCommandLine.test_rejection_returns_the_pr_comments_to_implement_and_keeps_the_note` runs the real CLI. It asserts the report line, the `implement` step and the `-m` note under the single `## Feedback`.
- 2: `rejected()` in `devteam/runner.py` and `pr_comments()` call `gh api <endpoint> --paginate` with no `--slurp` or `--jq`. Both tests assert the exact argv for owner, repo and number from the URL.
- 3, 10b: `render_pr_feedback` gives author (`unknown author` when `user` is missing or null), date (`submitted_at` for reviews, `created_at` otherwise), review state, and file and line. The outdated case renders as `line N (outdated)`, a file-level comment gets the file only, and an empty-body review is skipped. The pagination test uses concatenated arrays and asserts that `None` and `null` are absent.
- 4, 6: `questions.replace_section` swaps the section. Every body line is blockquoted using `splitlines()`. The hostile test covers `## Feedback`, a fenced `# comment`, a `## Pull request feedback` line and a lone `\r`. It checks two successive rounds, one heading of each kind, and `questions.parse == []`.
- 7, 10a: `test_endpoint_failures_and_invalid_pages` loops over all three endpoints for a non-zero exit (stderr shown), non-JSON, an object, `[1]`, a non-string body, trailing junk and empty output. It asserts the body is unchanged byte for byte, the step is still `rejected` and a second pass does nothing. The `ValueError` is converted to `StepFailed`.
- 8: The CLI test builds a `PATH` with only `git` and Python, and asserts `'gh'` in the OSError text. The runner-level test asserts `No such file or directory: 'gh'`.
- 9: `GH_TIMEOUT` is a module constant that the test lowers. `TimeoutExpired` becomes a `StepFailed` naming the call and the timeout.
- 10, 10c: A pending review and a review without `submitted_at` are skipped. The last URL is used, and the test asserts only `pulls/2` calls were made.
- 11: The section is parsed with a strict heading match and a `github.com` URL regex. The missing-URL tests assert the failure and that no `gh` call happened.
- 12: `test_rejection_of_a_pr_without_comments_says_so`, and the "no comments" text in `test_empty_feedback_and_prompt`.
- 13: `prompts/implement.md` names the heading and says the section holds the whole history with dates, that comments the code already meets need no change, and that the latest `## Feedback` note takes precedence. A test asserts the rendered prompt contains the heading.
- 14: The `HARNESS_ACTIONS` keys are unchanged, `merged` and the workflow JSON are untouched, and the harness full-suite run shows 140 tests OK. The edits to existing tests only add a PR URL and a stub for the new requirement.
- 15: Only `tests/stubs/gh` is used. The fixtures are tracked under `tests/fixtures/gh/`, one per endpoint. A test comment labels the baseline as modelled, not captured. Synthetic cases are inline. The diff has no stray files.
- 16: The README states that `gh` reads the comments, must be authenticated, and that a failure leaves the item at `rejected`.

Nothing in the diff lacks a criterion to justify it.
