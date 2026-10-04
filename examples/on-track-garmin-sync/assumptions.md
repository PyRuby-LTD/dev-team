# Assumptions

Everything here was inferred, not stated. Each entry says what would change the
answer. Resolved entries name the artifact that now owns the fact.

| # | Assumption | Why it matters | What would change it | Status | Owner |
|---|---|---|---|---|---|
| A1 | on-track is, or will be, multi-tenant with accounts per customer | Determines whether per-user delegated access to Garmin is needed | on-track staying single-user | **partly resolved** - commercial intent confirmed; current state of on-track's account model still unknown | architect |
| A2 | Sync cost becomes a recurring per-user unit cost carried by on-track | Sets a ceiling the architect must design to | a flat-fee or free arrangement with Garmin | open - customer has not yet given a per-user ceiling | architect |
| A3 | The existing FIT ingest API works and can be reused unchanged | Decides whether this touches on-track's core or only adds transport | ingest proving unsuitable for unattended delivery | open | architect |
| A4 | Each user must individually authorise on-track against their own Garmin account | Consent and cost are different things | Garmin permitting access without per-user consent | **resolved and extended** - the customer states it goes further: the user must also intentionally supply a personal access token from their on-track account. Recorded in `scope.md` and EPIC-003 | product owner |
| A5 | Garmin is the only device vendor in the first slice | A second vendor changes an integration into an abstraction | a cheap route covering many vendors at once | **resolved** - confirmed. See EPIC-004 | product owner |
| A6 | No external date or event constrains delivery | Affects how much is detailed up front | a launch commitment | open - not contradicted | delivery manager |
| A7 | Effort and cost must stay proportionate to the annoyance removed | Was the stop condition before the commercial clarification | sync becoming a differentiator worth real investment | **resolved** - sync is not the USP; on-track is a diet and exercise planner and running is one exercise among several. Recorded in `problem.md` | product owner |
| A8 | The upload path need not interpret FIT file contents; on-track can discard non-running activities | Removes FIT parsing from the transport entirely | on-track being unable to filter cheaply on receipt | **resolved** - offered by the customer and accepted. Recorded in `problem.md` | architect to confirm feasible |
| A9 | A personal access token step is acceptable during a hand-held beta but not at commercial launch | Sets when EPIC-003 must be done | the customer judging it acceptable commercially | open - inferred by the product owner, not stated | product owner |
| A10 | A mobile app must not be a precondition of slice 1, even though on-track wants one | A mobile app is a product; this is a feature | no viable route existing without one - in which case the cost is escalated, not absorbed | open - position taken by the product owner in `scope.md` | architect to test |
