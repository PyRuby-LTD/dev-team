# product/

What the team produces during discovery. Each artifact has exactly one owning
role; the owner is named in `team/`.

```
brief.md              your brief, verbatim                     delivery manager
engagement.md         running order, open questions and owners  delivery manager
problem.md            problem, audience, outcomes, non-goals    product owner
scope.md              first slice, minimum useful set, deferrals product owner
capabilities.md       capability map and journeys               product owner
epics/EPIC-NNN.md     blocks of value, with success criteria    product owner
stories/STORY-NNN.md  first slice only: stories and tech tasks  product owner / architect / platform
qualities.md          quality attributes as numbers            architect
architecture.md       components, data flow, boundaries        architect
decisions/ADR-NNN.md  decisions and what they cost us          architect
platform.md           environments, pipeline, observability    platform engineer
quality-strategy.md   what we check, where, and what we do not  quality lead
assumptions.md        everything inferred, and how to test it   everyone
plan.md               the sequenced first slice                 delivery manager
```

If an artifact contains something you did not say and have not confirmed, and
it is not in `assumptions.md`, that is a defect in the role that wrote it.
