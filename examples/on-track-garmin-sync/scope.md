# Scope: slices and deferrals

Owner: product owner. Deferred work is named with the reason and the trigger
that brings it back. Absence from this file is not deferral.

## Slice 1 - it works, for one athlete

An activity recorded on the customer's own Garmin watch reaches the on-track
API unattended, and something visibly confirms it arrived.

One user, hand-configured. Not a limitation to design around - it is the
smallest thing that proves the transport works at all. Stories cannot be
written for this slice until the architect settles the route off the watch;
writing them sooner would be fiction.

## Slice 2 - closed private beta

Twenty Reading Road Runners members. Installation, account creation and
configuring the upload are all done with hand-holding. Explicitly not
commercial, so onboarding may be manual and unpolished. (stated)

What slice 2 adds over slice 1: per-user setup repeated by someone who is not
the author, and the support load that reveals.

## Minimum useful set

Slice 1 plus slice 2. At that point the customer and twenty club members have
their activities arriving without a cable, which is the whole of the stated
frustration removed for real users.

## Deferred

| Work | Why deferred | What brings it back |
|---|---|---|
| Self-serve commercial onboarding | Beta is hand-held by agreement; commercial-grade signup is a different problem | deciding to sell on-track to the public |
| Replacing the personal access token step | See below - acceptable with hand-holding, probably not acceptable commercially | the same trigger as above |
| Apple, Coros, Polar devices | Garmin covers the customer and most of the trial cohort | a route that covers many vendors at once proving cheap, or the trial showing the cohort is not Garmin-dominated |
| Historic activity backfill | Not simple; needs investigation before it can be scoped | the spike below reporting |
| Per-user cost ceiling and whether sync is free or paid | Not commercial yet; the architect still needs a number to design against | the architect presenting route options with costs |

## Spike, not a story

**Can we establish what has already been uploaded?** The customer raised
backfill and rejected the simple answer. The underlying question is broader than
history: any unattended sync needs to know what it has already delivered, or it
will duplicate or drop activities. Questions to answer: can we track which files
have been uploaded, is there a reliable last-upload date, and is the answer the
same for historic activities as for new ones?

Owner: architect. This gates both backfill and the reliability of the main
flow, so it is not purely a deferred concern.

## The mobile app, and the position I am taking

on-track needs a mobile app for its own reasons. This work may be a catalyst
for it, and I am not treating it as a non-goal.

I am also not letting it become the justification. If the sync can be done
without a mobile app, the app decision stays separate and gets made on its own
merits. If the only viable route requires one, that is a finding I want in
front of the customer with its cost attached, not absorbed into this slice -
because a mobile app is a product, and this is a feature.

The architect is asked to evaluate routes both with and without a phone app,
and to price them separately.
