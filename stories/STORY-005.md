---
id: STORY-005
type: story
title: "Analyse a request with the team and create work items from it"
parent: EPIC-001
workflow: default
step: ready
---

# Analyse a request with the team and create work items from it

As the customer, I want to enter an idea, a new feature or a change, and have
the team question me until it understands it, so the epics, stories, tasks and
bugs come from my intent rather than from items I wrote by hand.

## Notes

Add a work-item type, `request`, stored in `requests/`. A request is small: the
first idea for a product is one, and so is each later feature, change of
audience or design change. The product evolves through many requests, not one
large brief. A request uses the same mechanism as every other item: `workflow`
names the JSON, `step` is its only state, and the runner and TUI need nothing
specific to it.

The product owner is the hub. From its step it can ask the customer questions,
pass the request to another role for input, or declare analysis complete. Every
role has its own analysis step and its own ask-the-customer step. Roles other
than the product owner cannot complete analysis; they can only hand the request
back to the product owner.

Proposed `workflows/analysis.json`:

```json
{
  "initial": "submitted",
  "steps": {
    "submitted":                   {"owner": "human",                   "transitions": {"analyse": "product-owner"}},

    "product-owner":               {"owner": "agent:product_owner",     "transitions": {
                                      "questions": "product-owner-questions",
                                      "architect": "architect",
                                      "platform-engineer": "platform-engineer",
                                      "quality-lead": "quality-lead",
                                      "complete": "review"}},
    "product-owner-questions":     {"owner": "human",                   "transitions": {"answered": "product-owner"}},

    "architect":                   {"owner": "agent:architect",         "transitions": {"questions": "architect-questions", "return": "product-owner"}},
    "architect-questions":         {"owner": "human",                   "transitions": {"answered": "architect"}},

    "platform-engineer":           {"owner": "agent:platform_engineer", "transitions": {"questions": "platform-engineer-questions", "return": "product-owner"}},
    "platform-engineer-questions": {"owner": "human",                   "transitions": {"answered": "platform-engineer"}},

    "quality-lead":                {"owner": "agent:quality_lead",      "transitions": {"questions": "quality-lead-questions", "return": "product-owner"}},
    "quality-lead-questions":      {"owner": "human",                   "transitions": {"answered": "quality-lead"}},

    "review":                      {"owner": "human",                   "transitions": {"approve": "done", "revise": "product-owner"}},
    "done":                        {"owner": "human",                   "transitions": {}}
  }
}
```

The request's body holds the customer's text, then each role's questions, the
answers and that role's findings, so the next owner reads what came before.
Before choosing `complete`, the product owner creates the epics, stories, tasks
and bugs through the existing capture code, each at its own workflow's initial
step, and lists them in the request body. The customer then reviews.

Changes needed: add `request` to the item types in `devteam/backlog.py`; add
`architect`, `platform_engineer` and `quality_lead` to `config/roles.toml` with
briefs drawn from the charters in `team/`; add a "new request" action to the
TUI; add a prompt for each agent-owned step.

Adding a specialist role to analysis later is two more steps and one more
product-owner transition in the JSON.

## Acceptance criteria

- Given the TUI, when the customer chooses "new request" and enters text, then a
  request file exists with that text as its body at the workflow's initial step.
- Given a request at `product-owner`, then the only moves available to that agent
  are asking the customer, passing to the architect, platform engineer or quality
  lead, or `complete`.
- Given a request at another role's step, then that agent can only ask the
  customer or `return` it to the product owner; a reply naming `complete` is
  refused and the step is unchanged.
- Given any role asks questions, then they are in the request body, the request
  is at that role's questions step, and after the customer answers it returns to
  the same role with the earlier content available.
- Given the product owner chooses `complete`, then the items it created are
  valid work items listed in the request body, and the request is at `review`.
- Given a request at `review`, when the customer chooses `revise`, then it
  returns to the product owner; when they choose `approve`, then it is `done` and
  none of the created items has moved beyond its own initial step.
- Given a request and a story in the same workspace, then each follows its own
  workflow file with no type-specific code in the runner or TUI.
- [human] Given a one-paragraph idea, when the customer goes through analysis,
  then the resulting work items reflect their answers.

## Feedback

- **rework -> analysis:** The step names here overlap with the default workflow steps, i.e. "review". The review step on analysis is owned by a human, but on the default workflow it's owned by an agent. There needs to be a way of disambiguating these workflows.
