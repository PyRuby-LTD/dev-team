---
id: STORY-002
type: story
title: "Run agent-owned steps"
parent: EPIC-001
workflow: default
step: implement
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
