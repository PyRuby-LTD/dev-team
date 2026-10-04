# EPIC-001 Unattended activity upload

**Status: closed, not proceeding** - 2026-09-25
**Reopens when:** the Garmin Connect Developer Program accepts new applications

## Vision
An activity recorded on a Garmin watch reaches the on-track API without the
athlete connecting the watch to a computer.

## Value
Removes the delay between finishing an activity and it being usable in a
training plan, and removes a manual step the athlete must remember.

## Scope
Transport only. Delivery of the FIT file to the existing on-track API endpoint,
authenticated as the owning user. The uploader does not interpret file
contents.

## Success criteria
- An activity finished away from home appears in on-track without the athlete
  doing anything afterwards
- The athlete can tell that it arrived, without checking the database
- An activity is not delivered twice, and is not silently lost

## Why it was closed

Every route was evaluated in `ADR-001` and `ADR-002`. The one that fits - the
Garmin Activity API - is closed to new applicants. The routes that remain either
cost more than they return, or degrade on-track's run analysis by dropping
splits and ground contact time, which are two of the five inputs it wants.

The customer's own position: the USB cable is connected for charging regardless,
so the residual cost is delay rather than effort, and that delay is tolerable.

**This is not a judgement that users do not want the feature.** Every serious
competitor has offered it for years and the demand is established. The problem
is access, not desirability. Closed as blocked, not as unwanted.

## What survives the closure

- `ADR-001` and `ADR-002` - the research is dated and evidenced, so it is not
  repeated when the programme reopens
- The iPhone app remains justified by other on-track features, and would resolve
  the personal access token problem in EPIC-003 as a side effect
- The data minimisation position - no height, weight, gender, or GPS routes -
  was validated with specifics and applies beyond this epic
- A quarterly check on the Garmin programme. An afternoon, and it is the whole
  epic if it lands.
