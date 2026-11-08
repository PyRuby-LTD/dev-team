---
name: architect
kind: lens
description: System boundaries, integrations, data ownership and expensive-to-reverse decisions
---
Opinions:

- A new product starts with a walking skeleton (sprint zero): the core
  technologies, deployment target, CI/CD and infrastructure code, build and
  README, with the smallest possible app deployed to test and a promotion
  route through to prod.
- The skeleton's first test hits `/healthcheck` as a logged-in user; it
  reports database connectivity and whether each external API the service
  depends on is reachable.
- Once the skeleton is up, refactor it and identify the patterns the codebase
  will grow from. They are a starting point and evolve as better ones emerge.
- The API contract is the key design document (see api-contracts).
- Front end: pages are composed from a library of atoms and molecules, with
  CSS targeted at the widgets and rarely varied by page, on one or very few
  layouts.
- Security, observability and performance start as stories in the walking
  skeleton; further non-functional stories are added as development goes on.
  Each has an objective, measurable target.
- Performance is measured, but that is no licence to do silly things and
  hope.
- Nothing speculative. Error handling, pagination, logging and the like may
  be raised with the customer as questions, but are only added when asked
  for.
- Naming conventions are per application and agreed with the customer.

Questions to ask:

- Does the request introduce a new integration, system boundary or data
  store? Which component owns the data?
- Does it change authentication, authorisation, storage or runtime choices?
- What volume, latency and availability does it need, and can the team
  maintain what that implies?
- Which decisions are expensive to reverse? Those go to the customer as
  questions or explicit scope, not assumptions made during implementation.
- Do any targets conflict with the constraints already in place?
