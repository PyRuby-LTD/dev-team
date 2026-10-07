---
id: STORY-013
type: story
title: Re-publish updates the existing PR
parent: EPIC-003
workflow: default
step: publish
---

Harness invocation examples updated for STORY-006; findings and recorded check
output below describe the original work. Replace `<checkout>` with the harness path.

As the customer, I want re-publishing after rejection to update the existing PR, so that I review one PR rather than several.

## Acceptance criteria

- When a PR already exists for the branch, the publisher pushes and updates it, records the same URL, and does not run `gh pr create` again.
- The `gh` calls the publisher needs are allow-listed in `config/roles.toml`.

## Analysis

### What exists today

- `workflows/default.json`: `publish` (agent:publisher) -> `pull-request` (human) -> `rejected` (harness) -> `implement` -> ... -> `accept` -> `publish`. A rejected item therefore reaches the publisher a second time on the same branch `devteam/<id>`.
- `devteam/runner.py` `invoke()`: because `[roles.publisher]` has `push = true`, the harness runs `git push -q -u origin <branch>` before every publisher run. On re-publish that is a fast-forward push of the new implement/test commits, and GitHub updates an open PR for that branch automatically. The publisher agent is told not to push or commit, and that stays.
- `prompts/publish.md` always says to run `gh pr create`, then record the URL under `## Pull request`. Nothing tells the agent to look for an existing PR, so a second run would try to create another PR (which `gh` rejects for a branch that already has an open PR, or creates a duplicate if the first was closed). That is the problem this story describes, and it does reproduce by reading the prompt.
- The item body keeps its `## Pull request` section across the rejection loop (the `rejected` action only replaces `## Pull request feedback`), so the existing URL is available to the publisher in the item it is given. `rejected()` reads the last URL in that section (STORY-012), so the section must keep a valid URL after re-publish.
- `config/roles.toml`: the claude engine's `--allowedTools` is `Bash(uv run --project <checkout> python -P -m devteam *) Bash(git diff *) Bash(git log *) Bash(git status *) Bash(gh pr create *)`. Only `gh pr create` is allowed, so an unattended publisher could not run any `gh` call needed to find or update an existing PR. The list is per engine, not per role, so any addition applies to every claude role. The `gh api` calls used by the `rejected` step run in the harness, not the agent, and need no allow-listing.
- `roles/publisher.md` says "Open a pull request"; it also needs to allow for an existing one.
- Tests: `tests/stubs/` has `claude`, `codex` and a `gh` stub that only serves `gh api` fixtures. No existing test covers the publisher prompt or the allow-list. `tests/test_merged_cli.py` already reads source files as text to assert on them, which is a precedent for prompt/config assertions.

### What would change

1. `prompts/publish.md`: before creating anything, look for a PR for `{{branch}}` (`gh pr list --head {{branch}} --state open --json url` or `gh pr view {{branch}} --json url,state`). Then:
   - An open PR exists: do not run `gh pr create`. The harness has already pushed, so the PR now shows the new commits; refresh its body from the current acceptance criteria, `## Implementation` and `## Review` with `gh pr edit`, and keep its title and URL.
   - No open PR exists (first publish, or the earlier PR was closed): run `gh pr create` as now.
   - Either way, the `## Pull request` section ends up holding the PR's URL, replacing the section's content rather than adding a second heading.
2. `roles/publisher.md`: one sentence saying the PR may already exist and is then updated, not recreated.
3. `config/roles.toml`: add to `--allowedTools` the `gh` subcommands the new prompt uses and no others, e.g. `Bash(gh pr list *)`, `Bash(gh pr view *)`, `Bash(gh pr edit *)`.
4. A test module that reads `prompts/publish.md` and `config/roles.toml` and asserts the points below; no network.
5. `README.md` line about publishing (around line 132 and 185): mention that re-publishing updates the existing PR.

### Assumptions (stated, not questions)

- "Updates it" means the push plus a refreshed PR body. Title is left alone, so the customer's edits to it survive; the body is regenerated because it quotes `## Implementation`, which changes after rework.
- If the earlier PR was closed rather than left open, a new PR is created and its URL recorded; the story's "same URL" applies only to an open PR. A merged PR is not reachable here (merge goes to `merged`, not back to `publish`).
- No harness (Python) change is needed: the push already happens and the URL lookup is the agent's job. If the customer wants the existing-PR check done deterministically in `runner.py` instead, say so, as that is a larger change.
- Merging remains out of scope; `gh pr merge` stays off the allow-list (`tests/test_merged_cli.py` asserts this for the sources it scans).

## Acceptance criteria (current)

1. `prompts/publish.md` tells the publisher to look for an existing open PR for `{{branch}}` before creating one, using `gh pr list` or `gh pr view`.
2. `prompts/publish.md` says that when an open PR exists the publisher does not run `gh pr create`, and instead updates the PR's body with `gh pr edit` and leaves its title and URL unchanged.
3. `prompts/publish.md` says that `gh pr create` is run only when no open PR exists for the branch.
4. `prompts/publish.md` still says not to run `git push` or `git commit`, and the harness still pushes the branch before the publisher runs (`push = true` on `[roles.publisher]`, unchanged).
5. `prompts/publish.md` says to record the PR URL under `## Pull request` by replacing that section's content, so that the section holds exactly one URL after a re-publish of an open PR and it is the same URL as before.
6. The `--allowedTools` string in `config/roles.toml` contains `Bash(gh pr list *)` and/or `Bash(gh pr view *)` (whichever the prompt uses to find the PR), `Bash(gh pr edit *)`, and still contains `Bash(gh pr create *)`. Every `gh` subcommand named in `prompts/publish.md` matches an allow-list entry, and no `gh pr merge` entry exists.
7. `roles/publisher.md` no longer states unconditionally that a PR is opened; it covers the existing-PR case.
8. A new unit test (run with `uv run python -m unittest`, offline) asserts criteria 1-3, 5 and 6 by reading the two files, and the existing suite still passes via `devteam check`.
9. `README.md` states that re-publishing after a rejection updates the existing PR.

## Challenge

Sound: a competent engineer could build this as written and a reviewer could tell whether they had. The claims about the code were checked against the repository and hold. Nothing below changes what gets built; the notes are for the customer to read before playing it.

Checked and confirmed:

- `prompts/publish.md` always runs `gh pr create` and never looks for an existing PR; `roles/publisher.md` says "Open a pull request" unconditionally.
- `config/roles.toml` allows only `gh pr create` of the `gh` subcommands, in a per-engine string shared by every claude role.
- `runner.py` `invoke()` pushes with `git push -q -u origin <branch>` before any `push = true` role runs, and `rejected()` takes the last URL under `## Pull request` and rewrites only `## Pull request feedback`.
- The open-PR case is the real path, not a guess: STORY-009 was rejected with review comments on PR #5 while it stayed open, and the same PR was later merged. Its item body still carries the `## Pull request` URL after the rejection.
- README lines 131-135 and 185-186 are the publishing text the item points at.

Notes, most significant first:

1. **Behaviour is only checked as prompt wording.** The customer's criterion is behavioural ("does not run `gh pr create` again", "records the same URL"); criteria 1-3, 5 and 8 verify that the prompt says so, not that the publisher does so. That is the honest limit of a prompt-only change and the item says the deterministic alternative (lookup in `runner.py`) is larger. The cheapest way to find out it is wrong: after this is built, reject one real PR and re-publish it, then confirm the PR number is unchanged and the publish log shows no `gh pr create`. STORY-013's own PR would do. This is a check to make at `pull-request`, not a reason to hold the item.
2. **The body refresh is the analyst's reading of "updates it", not the customer's words.** The push alone updates the PR's commits. Regenerating the body with `gh pr edit` overwrites anything the customer typed into the PR description, and it is the only reason `Bash(gh pr edit *)` is needed. The item states this as an assumption and the reasoning (the body quotes `## Implementation`, which changes) is fair. If the customer would rather the description were left alone, dropping it removes criterion 2's `gh pr edit` half and one allow-list entry.
3. **"Already exists" has been narrowed to "is open".** The customer's criterion says "when a PR already exists for the branch"; a closed PR also exists, and the item creates a second PR in that case rather than reopening. Stated as an assumption, and consistent with the README ("the tool does not merge or close the PR") and with how STORY-009 was actually rejected. Worth the customer knowing that closing a PR to reject it yields two PRs.
4. **The new `gh` entries apply to every claude role, not only the publisher.** The item says so. `gh pr edit *` also permits changing a PR's base, title, labels and reviewers. This matches how `gh pr create` is already granted, so it is no new kind of exposure, but it is wider than "the calls the publisher needs" might suggest.
5. **Criterion 1 leaves the lookup command to the implementer** (`gh pr list` or `gh pr view`). Either is fine and criterion 6 ties the allow-list to whichever is used. The prompt should give the full command including `--json`, since an unattended agent that pipes the output into `jq` or `grep` may fall outside the allow-listed pattern and be refused.

## Implementation

Updated `prompts/publish.md` to look up an open PR for the branch using `gh pr list --head {{branch}} --state open --json url` before creation. An existing open PR gets its body refreshed using `gh pr edit --body-file`, retaining its title and URL and skipping creation. Only a successful empty lookup leads to creation; lookup errors are reported. The item records exactly one URL by replacing the existing `## Pull request` section's content. Closed earlier PRs follow the specified new-PR path.

Added only `gh pr list` and `gh pr edit` to the existing Claude allow-list, retaining `gh pr create` and excluding merge. Updated the publisher role brief and README to describe re-publishing. The harness push and publisher `push = true` remain unchanged, as do the instructions prohibiting agent pushes and commits.

Added four offline unit tests in `tests/test_publish.py` covering lookup order and failure handling, update/create instructions, replacement of the recorded URL, and matching prompt commands to the parsed TOML allow-list.

Checks run, all exit code 0:

`uv run python -m unittest tests.test_publish`

```text
....
----------------------------------------------------------------------
Ran 4 tests in 0.004s

OK
```

`uv run --project <checkout> python -P -m devteam check tests.test_publish`

```text
uv run python -m unittest tests.test_publish
....
----------------------------------------------------------------------
Ran 4 tests in 0.003s

OK

check passed; full output: /home/tarttelin/projects/pyruby/dev-team/backlog/log/check/20261007T181617714558.log
```

`uv run python -m unittest tests.test_engines tests.test_runner tests.test_pr_feedback tests.test_merged_cli`

```text
...........................................
----------------------------------------------------------------------
Ran 43 tests in 18.991s

OK
```

`git diff --check`: no output, exit code 0.

No failures in these checks. The full suite is left to the runner after the tester's step, as instructed. These offline tests verify the prompt/configuration contract; live GitHub re-publishing is for the tester. No implementation work is blocked. Changes remain in the working tree without a commit.

## Tests

`tests/test_republish.py` drives the real runner through publish, rejection and a second publish on branch `devteam/<id>`. It uses the real `config/roles.toml`, `workflows/default.json`, `prompts/publish.md` and `roles/publisher.md`, real git repositories with a bare origin, and `tests/stubs/claude` (via a shim on PATH) as the engine. The stub records the argv the publisher was launched with. The prompt-text assertions in `tests/test_publish.py` are the implementer's and are kept. The publisher's behaviour with a live `gh` cannot be run offline; the tests show it is given the right instructions and permissions.

- Criterion 1 (lookup before create, via `gh pr list`): `test_second_publish_prompt_looks_up_the_open_pr_before_creating_one`
- Criterion 2 (no `gh pr create` when an open PR exists, `gh pr edit` instead): the same test
- Criterion 3 (create only when none exists): `tests/test_publish.py` `test_open_pr_is_edited_and_only_absent_open_pr_is_created`
- Criterion 4 (harness pushes, agent does not): `test_second_publish_pushes_new_commits_before_the_publisher_runs` and the "Do not run `git push`" assertion in the prompt test
- Criterion 5 (one URL, same URL): `test_item_keeps_its_single_pr_url_through_the_rejection_loop`, plus `tests/test_publish.py` `test_url_replaces_existing_section_content` for the prompt wording
- Criterion 6 (allow-list): `test_publisher_is_launched_with_the_gh_calls_it_needs_and_not_merge`
- Criterion 7 (role brief): `test_publisher_brief_covers_an_existing_pr`

Run one test: `uv run --project <checkout> python -P -m devteam check tests.test_republish.RepublishAfterRejection.test_publisher_is_launched_with_the_gh_calls_it_needs_and_not_merge`. Run the module: `uv run --project <checkout> python -P -m devteam check tests.test_republish`.

Full suite: 162 tests, OK.

## Test run

Run by the harness, 2026-10-07 18:22 UTC. Full output: `/home/tarttelin/projects/pyruby/dev-team/backlog/log/STORY-013/verify-20261007T182038431715.log`

Passed: `the project check`

```text
uv run python -m unittest discover -s tests
...............................................................................................................................Executing <Task pending name='screen_update' coro=<Timer._run_timer() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/timer.py:146> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.112 seconds
.Executing <Task pending name='message pump Actions()' coro=<MessagePump._process_messages() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/message_pump.py:571> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.133 seconds
...Executing <Task pending name="message pump Screen(id='_default')" coro=<MessagePump._process_messages() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/message_pump.py:571> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.126 seconds
..Executing <Task pending name="message pump Screen(id='_default')" coro=<MessagePump._process_messages() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/message_pump.py:571> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.198 seconds
.Executing <Task pending name='screen_update' coro=<Timer._run_timer() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/timer.py:146> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.114 seconds
.......Executing <Task pending name='message pump Header()' coro=<MessagePump._process_messages() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/message_pump.py:566> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.134 seconds
......Executing <Task pending name='message pump FooterKey()' coro=<MessagePump._process_messages() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/message_pump.py:571> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.135 seconds
...............
----------------------------------------------------------------------
Ran 162 tests in 96.266s

OK
```

## Review

No blocking findings. The change is sound for what a prompt-and-config change can deliver. Notes, most significant first:

1. `test_item_keeps_its_single_pr_url_through_the_rejection_loop` (tests/test_republish.py) proves less than its name says. The claude stub never edits the item body, so the assertion would hold with any publish prompt. Only the wording assertions in `tests/test_publish.py` (`test_url_replaces_existing_section_content`) stand behind criterion 5. Not blocking; the item names this as the limit of a prompt-only change. The real check is the one the Challenge suggests: reject a live PR, re-publish, and confirm the PR number is unchanged and no `gh pr create` appears in the log.
2. The prompt runs `gh pr list ... --json url` and leaves the agent to read the URL out of the JSON itself. That is correct under the allow-list (no `jq` or pipe is needed), but the prompt does not say how to pick the URL. Optional wording improvement.
3. `gh pr edit *` and `gh pr list *` now apply to every claude role, not only the publisher. This is the per-engine design the analysis already described, and it matches how `gh pr create` was already granted.

### Criteria
1. Met. `prompts/publish.md` step 1 runs `gh pr list --head {{branch}} --state open --json url` before creating anything. The test asserts the lookup comes before `gh pr create`, and the real runner test checks the rendered prompt.
2. Met. The prompt says "If an open PR exists, do not run `gh pr create`", uses `gh pr edit <existing-url> --body-file`, and leaves title and URL unchanged.
3. Met. The prompt says "Only when no open PR exists for the branch, run `gh pr create`". A failed lookup is reported, not treated as empty.
4. Met. The prompt still says not to run `git push` or `git commit`. `push = true` on the publisher is unchanged and asserted. `test_second_publish_pushes_new_commits_before_the_publisher_runs` checks the harness pushes the rework commit to the bare origin.
5. Met as wording. The prompt replaces the section's content and requires exactly one URL, the same as before when updating.
6. Met. `config/roles.toml` adds `Bash(gh pr list *)` and `Bash(gh pr edit *)` and keeps `gh pr create`. `test_all_prompt_gh_commands_are_allowed_without_merge` checks that the set of `gh pr` subcommands in the prompt equals the allow-list, and that merge is absent. The launched argv is also asserted.
7. Met. `roles/publisher.md` now covers updating an existing open PR or opening one.
8. Met. `tests/test_publish.py` covers criteria 1-3, 5 and 6 offline. The harness's full run passed (162 tests).
9. Met. README lines 131-135 and 185-188 state that re-publishing updates the existing open PR.

No scope creep: every part of the diff traces to a criterion.
