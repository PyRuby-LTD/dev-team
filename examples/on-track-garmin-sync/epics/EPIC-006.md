# EPIC-006 The post-run moment

**Status: considered and rejected, 2026-09-25**

Recorded so it is not re-proposed. Rejected on the customer's own reasoning,
which corrected the architect's.

## What was proposed

The customer's workaround for a closed sync epic was to screenshot Garmin
Connect's splits from a park bench and hand them to ChatGPT. The architect read
that as on-track being absent from the moment of highest engagement, and
proposed pursuing that moment.

## Why it was rejected

Garmin, Strava and Apple Health all deliver run data immediately after a run and
do it well. The post-run minute is served. A chatbot pep talk is pleasant and is
not a differentiator, and on-track competing there would be competing at
something three established products already do.

**on-track's value is longitudinal: taking several runs in the context of the
training block and reflecting on how the programme should adapt.** That is the
statement to design against, and it is not a post-run moment at all.

## What follows from it

The closure of EPIC-001 stands on firmer ground than the reasoning originally
given. If the value is longitudinal, immediacy is worth even less than the
delay-versus-faff argument assumed.

It also breaks the dependency the customer drew between run-data automation and
the LLM training-block review. That review needs data that is **complete**, not
data that is **immediate** - and a completeness gate is cheap, because on-track
already knows what was scheduled. Confidently wrong advice from an incomplete
picture is the risk worth designing against, and automated sync would not have
removed it, because sync fails silently too.

Candidate story for the review feature, product owner to take up: the review
refuses to run, or runs with an explicit caveat, when scheduled sessions since
the last review are unaccounted for.
