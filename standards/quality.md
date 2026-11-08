---
name: quality
kind: lens
description: Personas, the journeys they take and what must never happen
---
Opinions:

- Personas and their high-level descriptions live in a personas file in the
  product repository, alongside the journeys.
- Personas include the less obvious ones: the support team, and developers
  alerted to errors and reviewing logs.
- Front-end tests are expensive and make change hard: a small number of
  journeys exercise the main features.
- Wording and styling (labels, buttons, help text, layout) are judged by user
  testing, never asserted in automated tests.
- Many tests, one or more per acceptance criterion, many mocks, heavy set-up
  and a suite taking minutes are the anti-pattern to avoid.
- Acceptance criteria have no value once delivered; only the functionality in
  the application matters. A new criterion is often better served by changing
  an existing test than adding one.

Questions to ask:

- Who is affected by the request, including people who never use the user
  interface?
- Does it need a new persona, or change what an existing one does?
- Which user journeys does it change, extend or leave alone?
- What must never happen as a result of this change?
- What can be checked automatically, and what is left to user testing?
