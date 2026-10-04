# Brief: develop the reusable delivery team using its own roles

Owner: delivery manager. Captured 2026-10-02 from the customer conversation.
The following customer messages are verbatim. Analysis and proposed scope belong
in the other engagement artifacts, not inside these quotations.

## Original product intention

> My intention with this project is to create a development team that I as a customer can describe the product I want at a high level, including constraints such as deployment environment, tech stack constraints if any, anticipated user volumes, security requirements, performance targets etc. Given this broader context, different agents ask questions to create an initial "Walking skeleton" app including scripting all the infra, deployment pipelines etc, creating epics, stories and tasks to represent the different pieces. This is to create an initial sprint zero. From here, I want to describe the features I want to add one at a time so they can be captured as epics / stories etc, analysed, then played when I say I want them to be played. That gives me the choice about which features are priority and I can control the communication with users around releases. What I want this to be is a general case harness with agents defined and the flow of work sorted so I can reuse it across several products (each product may then add specialist agents where appropriate). Review what is there already and give me recommendations on how to build this out. I want a terminal UI that gives me visibility of what work is defined, what is being implemented, what is having tests added, what is being reviewed and what then is in automation test, then what is sat in a staging environment ready for me to user test.

## Build direction and storage constraints

> While github is a critical integration for me, linear is not something I've ever used but it seems popular at the moment. I don't really care if it's just in markdown files in a directory structure or tracked as github issues or whatever. The TUI should provide access to the stories / epics in any case, so it doesn't matter where they live, but they shouldn't depend on a local DB. I'm tempted to go back to basics and build it, using what is there at the moment so effectively building out the delivery team while simultaneously using the team as it exists so far. There are analysis gaps I need help to decide on to get started - how to capture the backlog of epic / story / task / bug and the state they are in for tracking them across stages of delivery.

## Authoritative documents and workflow

> hmm, I prefer the idea of using front-matter in the .md files as the golden source of all things to do with the work item. I'm tempted to define this as a workflow with each step in the flow defining which agent / human is responsible for the work in that step. It's only really a basic state machine for the python app to then invoke the appropriate agent role (could be a coordinating agent such as product owner could coordinate with architect, infra and test). It could be that analysis bounces back between analysis agent and human so questions get answered and the agent can then progress further.

## Owner-only workflow correction

> I don't think the workflow needs to define collaborators, just the owning agent / human. The owning agent makes their own decision on whether to coordinate with other agents. Other than that, this looks good to me. So the workflow would be controlled by a python program looping over the work items and acting on responses from agents or humans to move the item to the target step, then invoke the next agent / create a message for the human?

## Current commission

> Using the agent definitions, give the workflow and python controlling program info to the dev team to analyse and create epics / stories from

## Confirmed interpretation of the preceding discussion

- Reuse and evolve the current Python project and role definitions.
- Work-item Markdown front matter is the golden source of identity, hierarchy,
  current state, questions/answers, decisions, execution metadata and history.
  Narrative belongs in the body; large evidence may be linked, not a competing
  state store. The former proposal for authoritative sibling state.json files
  is superseded.
- Declarative workflow definitions name exactly one owning agent or human per
  step and map response outcomes to target steps. No collaborator list.
- Python validates responses and commits transitions, then dispatches the next
  agent or exposes a durable human request. Human waiting must not block other
  eligible work. Failures stay distinguishable from workflow progress.
- Ready-for-implementation and permission to implement are separate. Answering
  analysis questions does not mean play; release is separately controlled.
- The present request authorises analysis and backlog creation, not playing the
  resulting stories, invoking the legacy implementation pipeline, or publishing
  issues/messages to GitHub or another external service.

## Analysis instructions to the team

Use the source-of-truth charters under ../team/ and existing implementation under
../devteam/. Treat this harness as the product of this engagement. Produce a
small first slice around capture -> analysis -> human answer -> analysis -> ready
to play, with a minimal TUI and an explicit play boundary. Wider delivery,
GitHub/CI, staging, release, sprint-zero generation and specialist extensions
must remain visible as named later epics; do not silently discard them.

First-slice breadth and technical defaults are team proposals, not newly asserted
customer decisions. Record assumptions and owned open questions. Draft all work
items with machine-readable front matter and human-readable acceptance criteria;
mark them unplayed and pending customer prioritisation. These are proposed
schema records, not inputs compatible with today's state.json-based runner.

## Customer clarification: portable final product

> There are a number of references to .claude/agents/<some agent>.md or .claude/skills/<skill-name>/SKILL.md in the files. This feels like dependencies that leak from outside this repository. My preference is that the repo is self contained. What I want here is to check out the dev-team repo, add the command to run the python entrypoint or the TUI runner as an alias, then in the directory (initially an empty git repo checked out somewhere), I type the aliased command in, the TUI starts in the current directory and it's ready to go. It should have the same behaviour, agents, skills etc on whichever computer I check it out on.

> Note, this is part of specifying the final dev-team product so I'm not expecting the changes to be implemented, just captured in the appropriate story.

Captured in [STORY-010](stories/STORY-010.md), proposed and not played.
The existing `.claude` resources are repository-local; their current placement
does not itself demonstrate an external dependency. The requirement is explicit
resource ownership/resolution and portable launch, not an immediate file move.
