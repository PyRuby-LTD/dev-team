---
schema_version: 1
id: STORY-001
type: story
title: "Capture and validate linked Markdown work items"
parent: EPIC-001
state: implemented
authorisation: played
depends_on: []
owner: product-owner
x-session:
  customer_instruction: "play story ./workspace/stories/STORY-001.md"
  date: "2026-10-02"
  mode: controlled-implementation
  evidence: ../evidence/STORY-001.md
  verification: automated-checks-passed
---

# Capture and validate linked Markdown work items

As the customer, I want to capture and inspect work in readable files so I can trust its identity, hierarchy and status.

Include a proposed versioned schema for epic/story/task/bug, required fields, parent rules and dependency references. Runtime fields must eventually hold questions/answers, decisions, attempts and history in front matter; this planning schema alone is not that contract.

## Acceptance criteria

- [automated] Given valid fixtures for each supported type, when created and reopened, then unique IDs, parent/dependency links and text survive a round trip and only front matter supplies state. Evidence: schema and round-trip fixture results.
- [automated] Given duplicate IDs, missing parents, dependency cycles, malformed front matter or unsupported schema versions, when loaded, then actionable per-file errors are shown and affected work is ineligible for execution without silent repair. Evidence: negative fixture report.
- [automated] Given a newly captured item, when the scheduler scans it before an explicit customer Analyse action, then it remains unplayed and no agent is invoked or provider tokens spent, regardless of instructions in its description. Evidence: creation/idle-scan test with a recording fake engine.

## Refinement and evidence

Source: [brief](../brief.md). Proposals and open questions: [scope](../scope.md).
Implemented in a controlled session after the explicit customer play instruction
recorded above. [Evidence](../evidence/STORY-001.md) maps the checks to these
criteria and records scope decisions against architecture and quality guidance.
This remains a planning-schema record, not input to the prototype runner or
proof of verified runtime completion, customer acceptance or release.
