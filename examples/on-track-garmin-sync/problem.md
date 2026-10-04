# Problem, audience and outcome

Owner: product owner. Sources are marked: **stated** by the customer, or
**inferred** and logged in `assumptions.md`.

## The problem

Getting a recorded activity from a Garmin watch into on-track requires
connecting the watch to a laptop by USB, retrieving the FIT files, and pushing
them to the on-track API authenticated with a personal access token. The
activity therefore cannot reach on-track until the athlete is next at their
computer. (stated)

on-track is a diet and exercise planner. Running is one form of exercise it
covers, not its primary value. Sync being absent is a frustration, not a reason
the product cannot be sold. (stated - this corrected an earlier reading that
treated sync as a launch disqualifier)

## Audience

- Athletes following a structured plan in on-track who record activities on a
  Garmin device. (stated)
- First real cohort: members of Reading Road Runners, a club of 200+, with a
  closed trial of 20. (stated)
- Longer-term target: low thousands of users. Whether that volume affects this
  work depends on the upload route, which is the architect's question, not
  settled here. (stated)

## Outcome

An activity recorded on a Garmin watch reaches the on-track API without the
athlete connecting the watch to a computer.

The boundary is deliberate and narrow: **this work ends when the FIT file
reaches the API.** Matching an actual activity to a planned session is
on-track's existing responsibility and is not part of this. (stated)

A consequence the customer offered and we are taking: the upload path does not
need to interpret FIT file contents. on-track can discard an activity that is
not a run. The transport can be content-agnostic. (stated)

## Non-goals

- Matching activities to planned sessions - on-track already owns this
- **Any Strava integration, now or later.** Their commercial terms are not ones
  the customer will engage with. This is a constraint, not a preference (stated)
- Apple, Coros and Polar devices in this slice, though a route that covers all
  iPhone users at once is worth understanding if one exists (stated)
- Pushing planned workouts to the watch
- Live or in-progress activity tracking
- Replacing Garmin Connect in the athlete's own routine
- Activity types other than running being *stored*; filtering is on-track's job,
  not the uploader's (stated)

## Not a non-goal

A mobile app. on-track will need one regardless, some existing functionality is
already degraded without one, and this work could be a catalyst for it. (stated)
See `scope.md` for the position the product owner takes on that.
