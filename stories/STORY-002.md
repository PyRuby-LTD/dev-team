---
id: STORY-002
type: story
title: "Run agent-owned steps"
parent: EPIC-001
workflow: default
step: done
---

# Run agent-owned steps

As the customer, I want Python to hand each item to the right agent whenever
its current step is agent-owned, so work moves without me driving every stage.

## Notes

Add `devteam run --workspace W`: loop over the work items; for each one whose
step is owned by `agent:<role>`, invoke that role using its engine and model
from `config/roles.toml`, passing the role brief, the item file and the names
of the valid transitions. Reuse `devteam/engines.py`; it currently takes a
legacy `WorkItem`, so adapt it to a Markdown record. Step prompts live in
`prompts/<step>.md`.

The agent may edit the item's body, for example adding questions under a
`## Questions` heading, but not its front matter. Its reply ends with a line
`TRANSITION: <name>`. Python checks the name against the step's transitions and
moves the item (STORY-001). The transcript of every invocation is written under
`W/log/<item id>/`.

Prove the loop on `analysis` first. `implement` and `review` need the worktree
and branch handling now in `devteam/pipeline.py`; carry that over, then retire
`pipeline.py`, `workitem.py` and the legacy `new/step/run/show/decide/clean`
commands, which this replaces.

Out of scope: attempt identities, replay protection, crash reconciliation and
permission sandboxes beyond what the engine templates already apply.

## Acceptance criteria

- Given an item at an agent-owned step, when the runner passes over it, then the
  owning role's configured engine and model are invoked once with the item and
  its valid transition names. Checked with a fake engine.
- Given the agent's reply names a valid transition, then the item's step becomes
  the target, and the next pass acts on the new step's owner.
- Given a nonzero exit, or a reply with a missing or unknown transition, then the
  step is unchanged, the failure and its log path are reported, and the item is
  not retried until the runner is restarted.
- Given an item at a human-owned or terminal step, then no agent is invoked.
- Given one item waiting on the human and another at an agent-owned step, when
  the runner loops, then the second progresses.
- Given the analyst needs clarification, when it finishes, then its questions are
  in the item body under `## Questions` and the item is at `answering`.

## Review

Outcome: revise.

- `git diff main...devteam/STORY-002` is empty. The branch tip (1d36194) is the same commit as `main`, and the working tree is clean. There is no change to judge against the acceptance criteria.
- `devteam/runner.py` and a `run` subcommand already exist on `main`, and `pipeline.py` and `workitem.py` are already gone. If that earlier work is what satisfies this story, this branch does not show it. Nothing here proves the six criteria (fake-engine invocation, valid transition, failure and no retry until restart, human-owned or terminal steps skipped, a waiting item not blocking another, analyst `## Questions` leading to `answering`).
- Trigger: review the branch as it stands. Result: no code, no tests and no evidence for any criterion. Either commit the implementation and tests to this branch, or show which commits on `main` already deliver the story.

## Implementation

Addressed the review by identifying the existing delivery commits and adding
code and acceptance coverage on `devteam/STORY-002`. The initial Markdown
runner, fake-engine tests, prompt protocol, logging, and retirement of
`pipeline.py`, `workitem.py`, and legacy commands landed in
`4fcf390f75d1217d18414f81239682cfd0ed9e51` on main. Checkout and branch
handling landed in `402dd42409134671f8a044e187569095278bd610` on main.

Changes in this working tree:

- Added `run --workspace W`, using W as the item root and W/log as the
  transcript root while retaining the product checkout for branch-owning roles.
- Skip terminal steps even when their configured owner is an agent.
- Ensure engines whose argv template omits `{brief}` receive the role brief
  at the start of their prompt (including the configured Codex engine).
- Restore the original front matter after agent tampering, including invalid
  YAML, equivalent YAML rewrites, and nonzero engine exits. Preserve body edits
  when the front-matter delimiters remain; otherwise restore the original file.
- Expanded fake-engine checks for configured engine/model and transition names,
  implementation-to-review dispatch on consecutive passes, actual terminal
  records, restart after failures, transcripts, and a pre-existing human wait
  that does not block another item. The analyst questions test proves body
  edits survive the transition to answering and subsequent human answers.
- Documented workspace selection, brief delivery, and header restoration.
  Existing checkout tests verify implementer/reviewer invocation on the item
  branch, checkout ownership, waiting behavior, and base-branch handling.

Actual checks (Python 3.13.7, pinned dependencies in .venv):

`.venv/bin/python -m unittest discover -s tests -p test_runner.py -v`

```text
Ran 14 tests in 0.400s

OK
```

`.venv/bin/python -m unittest discover -s tests -p test_backlog.py -v`

```text
Ran 11 tests in 0.151s

OK
```

`.venv/bin/python -m unittest discover -s tests -p test_workflow.py -v`

```text
Ran 8 tests in 0.054s

OK
```

`.venv/bin/python -m unittest discover -s tests -p test_checkout.py -v`

```text
Ran 9 tests in 2.119s

OK
```

`PYTHONPATH=tests .venv/bin/python -m unittest test_tui.ViewModel test_tui.QuestionParsing -v`

```text
Ran 6 tests in 0.140s

OK
```

Full-suite command: `.venv/bin/python -m unittest discover -s tests -v`.
All backlog, checkout, and runner tests printed `ok`; it then stalled after:

```text
test_agent_owned_and_finished_items_offer_nothing (test_tui.Acting.test_agent_owned_and_finished_items_offer_nothing) ... ok
```

The baseline suite before edits stalled at the same place. Both runs were
interrupted (exit 130). An isolated TUI run with a 45-second timeout exited
124. A faulthandler trace showed the stall in `asyncio.runners.Runner.close`,
line 72, waiting for `loop.shutdown_default_executor()` after the test's
assertions completed. This pre-existing cleanup issue prevents claiming a
passing full suite in this environment. The 48 tests listed above completed
successfully. No unrelated TUI code was changed.

`.venv/bin/python -m compileall -q devteam tests`: exit 0, no output.
`git diff --check` and `git -C backlog diff --check`: exit 0, no output.
`.venv/bin/python -m devteam backlog validate`: exit 0; includes:

```text
STORY-002  implement    agent:implementer  Run agent-owned steps
```

`.venv/bin/python -m devteam run --help`: exit 0; usage:

```text
usage: devteam run [-h] [--workspace WORKSPACE] [--once]
```

Commit limitation: `git add README.md devteam/cli.py devteam/engines.py
devteam/runner.py tests/test_runner.py` and the requested `git commit` both
failed with:

```text
fatal: Unable to create '/home/tarttelin/projects/pyruby/dev-team/.git/index.lock': Read-only file system
```

The session explicitly mounts `.git` read-only and disallows permission
escalation. Changes are therefore uncommitted on `devteam/STORY-002`, whose
HEAD remains `1d36194`. This also blocks completing the review's request for
a committed branch diff. The work item front matter has been preserved.
