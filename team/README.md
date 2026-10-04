# The team

Five roles, each accountable for a different kind of wrong answer. A role is
defined by its charter in this directory; the charter is the source of truth,
and the tooling under `.claude/` only says how to convene that person.

| Role | Accountable for | The mistake they exist to prevent |
|---|---|---|
| [Delivery manager](delivery-manager.md) | the engagement: what happens next, what is blocked, what was decided | drifting discovery that never reaches a deliverable |
| [Product owner](product-owner.md) | problem, audience, outcomes, non-goals, what "done" means | building the wrong product competently |
| [Architect](architect.md) | system shape, quality attributes, decisions and their consequences | over-building for imagined scale, or discovering a constraint too late |
| [Platform engineer](platform-engineer.md) | environments, pipeline, observability, rollback, running cost | a system that works on a laptop and nowhere else |
| [Quality lead](quality-lead.md) | how we prove a thing is done, and what we can check without a human | acceptance criteria that read well and decide nothing |

## The workspace

This repository is the team, not any one product. Everything a role produces
goes to the **engagement workspace** - a directory named in `config/workspace`,
pointing at the product being worked on. Change it with `tools/workspace <path>`
to put the same team on a different product.

`examples/on-track-garmin-sync/` is a completed engagement kept as a worked
example of the output. It is not this repository's content.

## How an engagement runs

1. You bring a brief. The **delivery manager** takes it, records it verbatim,
   and says who needs to talk to you and in what order.
2. The **product owner** interviews you on the problem, the audience and what
   changes for them. Output: `<workspace>/problem.md` and the epics.
3. The **architect** and **platform engineer** interview you on constraints -
   volumes, latency, hosting, data sensitivity, budget. Output:
   `<workspace>/qualities.md`, `<workspace>/architecture.md`, `<workspace>/platform.md`,
   and an ADR per decision that has real consequences.
4. The **quality lead** turns the product owner's intent into criteria that can
   be checked, and flags the ones that will always need your eyes.
5. The **product owner** and **delivery manager** decompose the first slice into
   stories and tech tasks, and sequence them.

Steps 2-4 interleave. An architect will surface a constraint that changes the
product; that goes back to the product owner rather than being absorbed quietly.

## Two rules every role follows

**Separate what you were told from what you assumed.** Anything the customer
did not say and has not confirmed belongs in `<workspace>/assumptions.md`, with what
would change the answer. An artifact that presents an inference as a fact is
defective.

**Decide the foundations once; deepen functional detail just in time.** The
technical shape - runtime and language, auth, storage, third-party services,
hosting, build pipeline - is settled during discovery. Every story inherits
these and they are expensive to revisit, so they get enough up-front thinking to
be decided properly, with the reasoning recorded as ADRs.

Functional scope works the other way. Discovery identifies the first slice, the
minimum useful set of features, and what is deliberately deferred. The first
slice is broken down into stories; deferred work stays a named epic and is not
decomposed further until something has shipped and taught us whether it is still
the right thing. Deferral is recorded in `<workspace>/scope.md` with the reason -
never left implied by absence.
