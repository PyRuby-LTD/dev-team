---
schema_version: 1
id: STORY-007
type: story
title: "Inspect backlog and current responsibility in the terminal"
parent: EPIC-003
state: proposed
authorisation: not-played
depends_on: ["STORY-001","STORY-004"]
owner: product-owner
---

# Inspect backlog and current responsibility in the terminal

As the customer, I want a terminal view of the backlog and each item's current situation so I can decide where to focus.

Provide list/detail navigation showing hierarchy, workflow state, execution failure/wait, owning role, authorisation, outstanding questions and evidence/history links. Derive views from front matter; any cache is disposable and non-authoritative.

## Workflow-driven presentation

Resolve each item's front-matter workflow ID/version/digest using STORY-004's
registry, then map its `state` through that pinned JSON definition. Use the
state's presentation group, label, order and semantic style for the TUI rather
than hard-coded lifecycle names. Several states may share a display group, but
the detail view must retain the exact state, workflow identity and sole owner.
Items using different workflows must retain their respective mappings and
available actions; sharing a group label does not make their states equivalent.

Show execution status (running, failed, uncertain or waiting) separately from
business state. Derive actions from validated outcomes, guards and the current
actor, never from display labels or styles. Preserve text labels and keyboard
access so colour is not the only indication of state or required human action.
Use the bundled default to show the full intended delivery journey, clearly
marking stages unavailable in the current slice without suggesting that work
has run there. Missing or invalid workflow bindings remain inspectable as
diagnostics; the TUI must not guess an owner, transition or replacement workflow.

## Acceptance criteria

- [automated] Given items bound to different validated JSON workflows, when the TUI renders them, then each uses its pinned state's group, label, order and style, and detail views show the exact state, workflow identity and owner; multiple states may share a group without losing their identities. Evidence: multi-workflow view-model and render fixtures.
- [automated] Given a separately versioned fixture with changed presentation metadata but unchanged transition rules, when rendered, then its grouping and display change as specified while available actions, guards and transition results remain unchanged; existing items retain their pinned version. Evidence: presentation/transition separation tests.
- [automated] Given running, failed or uncertain attempts and unavailable later delivery capabilities, when displayed, then execution indicators remain distinct from business state and unavailable stages/actions are clearly identified without advancing or dispatching work. Evidence: status-overlay and capability render fixtures.
- [human] Given the default workflow in a terminal without colour, when navigating the backlog and state details by keyboard, then the customer can distinguish stages, exact states, owners and required human actions using text alone. Evidence: accessible terminal walkthrough.
- [automated] Given a mixed fixture backlog, when the TUI opens or refreshes, then list/detail views agree with front matter and distinguish proposed, analysing, human-waiting, ready/unplayed and failed work. Evidence: view-model/render snapshots.
- [automated] Given malformed or unresolved records, when the view loads, then diagnostics identify affected files while valid records remain inspectable and unsafe actions are unavailable. Evidence: mixed-validity view test.
- [automated] Given a running coordinator and an outstanding human request or uncertain attempt, when the TUI disconnects and reconnects, then it reconstructs the same current state from committed records without cancelling execution, answering requests or granting permissions. Evidence: headless reconnect fixture and front-matter comparison.
- [human] Given an epic with stories and an outstanding question, when the customer navigates by keyboard, then they can find the owner, question, authorisation and evidence without reading raw files. Evidence: observed walkthrough with review notes.

## Refinement and evidence

Source: [brief](../brief.md). Proposals and open questions: [scope](../scope.md). Reconcile with intended [architecture](../architecture.md), [qualities](../qualities.md) and [quality strategy](../quality-strategy.md) before play. These criteria specify future evidence, not completed tests. This is a proposed planning record, not an input compatible with the prototype runner.
