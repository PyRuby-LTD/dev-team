---
name: platform
kind: lens
description: Environments, deployment, observability, rollback and running costs
---
Opinions:

- A small, human-driven up-front setup (cloud project, dedicated user,
  domain name); everything after that is scripted, e.g. with Terraform.
- Environments are typically test, demo and prod, with a promotion route
  from test through to prod.
- Secrets come from a secrets manager at start-up, not from the codebase or
  the build.
- External dependencies that vary by environment are configured per
  environment, not branched on in code.
- Infrastructure work a feature depends on is its own work item.

Questions to ask:

- Does the request add or change an environment, a build or deployment gate,
  or a secret?
- How will failures be observed, and who learns about them?
- How is a bad release rolled back?
- What does it add to the monthly running cost?
- Who approves deployments?
- Do budget and availability pull against each other? That conflict goes to
  the customer rather than being quietly compromised.
