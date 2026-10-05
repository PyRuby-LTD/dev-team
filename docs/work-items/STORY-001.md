---
id: STORY-001
type: story
title: "Define the workflow in JSON and track each item's step"
parent: EPIC-001
workflow: default
step: done
---

# Define the workflow in JSON and track each item's step

As the customer, I want the workflow held in one JSON file so I can see and
change who owns each step and where an item can go next.

## Notes

Add `workflows/default.json` to the dev-team repository and a small loader
(`devteam/workflow.py`). A workflow has an `initial` step and a map of steps.
Each step names exactly one owner, either `human` or `agent:<role>` where the
role is a key in `config/roles.toml`, and its transitions as name -> target
step. A step with no transitions is terminal.

Proposed default, using the roles that already exist:

```json
{
  "initial": "captured",
  "steps": {
    "captured":  {"owner": "human",             "transitions": {"analyse": "analysis"}},
    "analysis":  {"owner": "agent:analyst",     "transitions": {"questions": "answering", "ready": "ready"}},
    "answering": {"owner": "human",             "transitions": {"answered": "analysis"}},
    "ready":     {"owner": "human",             "transitions": {"play": "implement", "rework": "analysis"}},
    "implement": {"owner": "agent:implementer", "transitions": {"implemented": "review"}},
    "review":    {"owner": "agent:reviewer",    "transitions": {"approve": "accept", "revise": "implement"}},
    "accept":    {"owner": "human",             "transitions": {"accept": "done", "revise": "implement"}},
    "done":      {"owner": "human",             "transitions": {}}
  }
}
```

A work item's front matter is `id`, `type`, `title`, `parent`, `workflow` and
`step`. `workflow` names the JSON file; `step` is the only state. Epics carry
neither. `devteam/backlog.py` checks both against the loaded definition and
capture uses the workflow's `initial` step.

Out of scope: workflow versions or digests, guards, display metadata, history
or revisions in front matter. Git history is the audit trail.

## Acceptance criteria

- Given the default workflow, when it is loaded, then every step has exactly one
  owner and every transition targets a defined step; a definition that breaks
  either rule is rejected with a message naming the step.
- Given a step owned by `agent:<role>` where the role is not in
  `config/roles.toml`, when the workflow is loaded, then it is rejected naming
  the role.
- Given an item whose `workflow` or `step` is not defined, when
  `devteam backlog validate` runs, then the file is reported and the item is not
  offered for any action.
- Given an item and one of its step's transition names, when the transition is
  applied, then `step` becomes the target and the body is unchanged byte for
  byte; any other name is refused and the file is untouched.
- Given a new item is captured, then its `step` is the workflow's `initial`.

## Review

`git diff main...devteam/STORY-001` is empty: the branch tip (18848f3) is the
same commit as main, so this change adds nothing to review. The criteria are
already met by code on main (commit 4fcf390), which I read directly:

- Owner and target-step rules: `devteam/workflow.py` `build` rejects bad owners
  and undefined transition targets with the step name in the message.
- Unknown role: rejected with the role named (`role 'x' is not in config/roles.toml`).
- Undefined `workflow` or `step`: `Backlog.step` raises and the validate pass
  reports the file (`devteam/backlog.py` around lines 186-211).
- Transition: only the `step:` line is rewritten, the body is checked unchanged,
  and unknown names are refused with the file untouched (lines 275-291).
- Capture uses `workflow.initial` (line 235).

`tests/test_workflow.py` has a test per criterion. I could not run the suite in
this session (command needs approval), so passing tests are unverified.

No defects found in the existing code. Approving on the basis that nothing
further is needed for this item; if a distinct change was expected on the
branch, it was not committed.
