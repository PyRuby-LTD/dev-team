---
schema_version: 1
id: STORY-010
type: story
title: "Launch a self-contained team against the current product directory"
parent: EPIC-001
state: proposed
authorisation: not-played
depends_on: ["STORY-007"]
owner: product-owner
---

# Launch a self-contained team against the current product directory

As the customer, I want to check out dev-team once, alias its launcher, and run
that command from any product repository, including an empty Git repository,
so the TUI opens for that product with the same bundled team on each computer.

## Scope

Separate the harness resource root from the product root. Resolve shipped agent
definitions, skills, workflows, prompts and supporting resources from the
dev-team checkout/package; default the product root to the invocation directory.
The alias must not change into the harness directory. Do not require copying
team definitions into every product or configuring a shared `config/workspace`.
Keep product work items and their authoritative front matter in product-local
Markdown files, with no required local database. Exact subdirectory names and
packaging/launcher mechanics remain implementation design choices.

Existing `.claude/agents/...` and `.claude/skills/...` references name files inside
this repository, not necessarily external dependencies. Nevertheless, the final
product must resolve its complete resource set explicitly and must not depend
on a user's home-directory agents, skills or provider-specific project discovery.
Provider-specific wrappers may exist, but are not the canonical source of team
behaviour. Audit transitive resource references as well as the top-level files.

Document runtime/provider prerequisites and credential setup separately from
bundled team resources; self-contained does not mean shipping credentials,
Python, model services or provider executables. Matching supported environments,
harness revision and product configuration should resolve the same definitions
and rules, not promise identical probabilistic model outputs. Product specialist
extensions remain later scope; no silent global overrides of the core team.

## Acceptance criteria

- [automated] Given a checkout outside a product repository and the documented launcher/alias, when invoked from that product directory, then the TUI opens for that directory and resolves all core resources from the harness, without changing the working directory or requiring a shared workspace setting. Evidence: outside-checkout launch integration test.
- [automated] Given an empty Git repository without a first commit or product configuration, when launched, then the TUI offers onboarding and an empty backlog without requiring HEAD, worktrees, copied agent files or a local database, and without starting agents or implementation. Evidence: empty-repository bootstrap test with a recording fake engine.
- [automated] Given two supported clean environments with the same harness revision and product configuration and no user-installed skills or agents, when resource resolution and a fake-engine workflow run, then the same resource identities, contents and workflow transitions are used, including all referenced supporting files. Evidence: isolated-environment portability and resource-closure tests.
- [automated] Given two product directories using one harness checkout, when each is opened and its backlog edited, then work items and state remain in the selected product and neither the other product nor bundled harness resources are modified. Evidence: two-product isolation and front-matter reload tests.
- [automated] Given missing provider credentials or executables, when the TUI opens and analysis is requested, then backlog inspection remains available and analysis reports an actionable prerequisite error without falsely advancing the item. Evidence: missing-prerequisite integration tests.
- [human] Given the documented prerequisites and a fresh checkout on a supported computer, when the customer follows setup and aliases the entrypoint, then launching from an empty product repository requires no undocumented home-directory resources or machine-specific source edits. Evidence: recorded clean-setup walkthrough.

## Delivery boundary

This story specifies the final product only. It is proposed and not played; it
does not authorise relocating existing definitions, changing the current runner,
installing tools or creating an alias now. It follows STORY-007 for end-to-end
TUI acceptance; resource and launcher design can be refined earlier.

Source: [brief](../brief.md). Parent: [EPIC-001](../epics/EPIC-001.md).
Related design: [architecture](../architecture.md), [platform](../platform.md).
Acceptance criteria describe future evidence, not tests already completed.
