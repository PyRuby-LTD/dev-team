# Engagement

Brief received 2026-09-25, with a commercial clarification the same day. The
clarification materially changed the engagement: this is a feature of a product
intended for sale, not a personal utility.

## What the clarification changed

- **Users.** Not one. Auth cannot be a personal access token held by the person
  who wrote the code; it becomes delegated access per customer.
- **Cost.** No longer a hobby ceiling. Costs are borne by on-track and become a
  per-user unit cost that scales with customers.
- **Terms.** Whether Garmin permits this at all now depends on commercial terms
  rather than personal use. That is a gating question, not a detail.

## Running order

Out of the usual sequence. The brief is functionally narrow but the dominant
uncertainty is whether the data can leave the watch on acceptable commercial
terms, and that gates whether there is a product here at all.

| # | Role | Purpose | Waiting on |
|---|---|---|---|
| 1 | Product owner | Outcome, non-goals, vendor scope, backfill, where sync sits commercially | nothing - ready |
| 2 | Architect | Transport off the watch, Garmin terms, delegated auth, cost model, on-track's current stack | product owner round 1 |
| 3 | Platform engineer | Environments, pipeline, observability, running cost per user | architect |
| 4 | Quality lead | How we prove a run synced, and what needs human eyes | product owner and architect |
| 5 | Product owner + delivery manager | First slice, deferrals, sequencing | all of the above |

## Open questions

| # | Question | Owner | Raised |
|---|---|---|---|
| Q1 | What does Garmin's developer programme permit for commercial use, at what cost, and how long does approval take? | architect | 2026-09-25 |
| ~~Q2~~ | Answered: yes for activities; setup is hand-held in beta. See scope.md | product owner | closed |
| ~~Q3~~ | Answered: deferred, gated on a spike. See EPIC-005 | product owner | closed |
| ~~Q4~~ | Answered: Garmin only; Strava permanently excluded. See EPIC-004 | product owner | closed |
| Q5 | What is on-track's stack, hosting, and is its API publicly reachable? | architect | 2026-09-25 |
| Q6 | What per-user monthly cost is acceptable? Commercial model deferred, but the architect needs a ceiling | product owner | 2026-09-25 |
| ~~Q7~~ | Answered: yes, and the user also supplies an on-track PAT. See EPIC-003 | product owner | closed |

## Risks

**R1 - owned by the architect.** The routes for getting data off a Garmin watch
without a cable differ by orders of magnitude in cost, approval time and
ongoing maintenance, and not all are open on commercial terms. Until this is
settled, any estimate of the first slice is fiction. To be answered in the
architect's first session, not discovered later.

**R2 - owned by the product owner.** A commercial product implies customers who
are not the author. Anything designed around one person's watch, one person's
tolerance for setup, and one person's account is likely to be rebuilt.

## Added after the product owner session

| # | Question | Owner | Raised |
|---|---|---|---|
| Q8 | Does a route exist that covers all iPhone users at once, and what would it cost? | architect | 2026-09-25 |
| Q9 | Can we establish what has already been uploaded - by file, by last-upload date, or not at all? Spike. | architect | 2026-09-25 |
| Q10 | What do the routes cost with and without a mobile app, priced separately? | architect | 2026-09-25 |
| Q11 | What is on-track's current account model - single user, or accounts per customer already? | architect | 2026-09-25 |

## Engagement closed, 2026-09-25

EPIC-001 closed as blocked, not unwanted. Reasoning in the epic; evidence in
ADR-001 and ADR-002.

Discovery ran one day and established that the work should not be built yet.
No stories were written, which was the correct outcome - writing them would have
required a transport decision that could not be made.

### Residual actions

| Action | Owner | When |
|---|---|---|
| Check whether the Garmin Connect Developer Program has reopened | customer | quarterly |
| Apply the day it reopens - free, and it makes every other route redundant | customer | on reopening |
| Confirm on-track's Cloud Run region is UK or EU | architect | next time the stack is touched |
| ~~Revisit EPIC-006~~ - considered and rejected by the customer; see the epic | product owner | closed |

### Closed without being answered

Q6 - per-user cost ceiling was given as GBP 10 falling with scale, but no route
survived to design against it.
Q9 - the delivery-state spike was never run; it returns with the epic.
Q10 - mobile app pricing was answered by the app being justified elsewhere.

### The finding that outlived the engagement

on-track's value is longitudinal: several runs read in the context of the
training block, and a view on how the programme should adapt. Not the post-run
moment, which Garmin, Strava and Apple Health already serve well.

Stated by the customer while rejecting EPIC-006. It is a sharper positioning
statement than anything the engagement produced deliberately, and it belongs in
whatever brief the LLM training-block review is built from.
