# Brief: develop the reusable delivery team using its own roles

Owner: delivery manager. Captured 2026-10-02 from the customer conversation.
The following customer messages are verbatim. Scope and the backlog live in
[scope](scope.md), [epics](epics/) and [stories](stories/).

## Original product intention

> My intention with this project is to create a development team that I as a customer can describe the product I want at a high level, including constraints such as deployment environment, tech stack constraints if any, anticipated user volumes, security requirements, performance targets etc. Given this broader context, different agents ask questions to create an initial "Walking skeleton" app including scripting all the infra, deployment pipelines etc, creating epics, stories and tasks to represent the different pieces. This is to create an initial sprint zero. From here, I want to describe the features I want to add one at a time so they can be captured as epics / stories etc, analysed, then played when I say I want them to be played. That gives me the choice about which features are priority and I can control the communication with users around releases. What I want this to be is a general case harness with agents defined and the flow of work sorted so I can reuse it across several products (each product may then add specialist agents where appropriate). Review what is there already and give me recommendations on how to build this out. I want a terminal UI that gives me visibility of what work is defined, what is being implemented, what is having tests added, what is being reviewed and what then is in automation test, then what is sat in a staging environment ready for me to user test.

## Build direction and storage constraints

> While github is a critical integration for me, linear is not something I've ever used but it seems popular at the moment. I don't really care if it's just in markdown files in a directory structure or tracked as github issues or whatever. The TUI should provide access to the stories / epics in any case, so it doesn't matter where they live, but they shouldn't depend on a local DB. I'm tempted to go back to basics and build it, using what is there at the moment so effectively building out the delivery team while simultaneously using the team as it exists so far. There are analysis gaps I need help to decide on to get started - how to capture the backlog of epic / story / task / bug and the state they are in for tracking them across stages of delivery.

## Authoritative documents and workflow

> hmm, I prefer the idea of using front-matter in the .md files as the golden source of all things to do with the work item. I'm tempted to define this as a workflow with each step in the flow defining which agent / human is responsible for the work in that step. It's only really a basic state machine for the python app to then invoke the appropriate agent role (could be a coordinating agent such as product owner could coordinate with architect, infra and test). It could be that analysis bounces back between analysis agent and human so questions get answered and the agent can then progress further.

## Owner-only workflow correction

> I don't think the workflow needs to define collaborators, just the owning agent / human. The owning agent makes their own decision on whether to coordinate with other agents. Other than that, this looks good to me. So the workflow would be controlled by a python program looping over the work items and acting on responses from agents or humans to move the item to the target step, then invoke the next agent / create a message for the human?

## Customer clarification: portable final product

> There are a number of references to .claude/agents/<some agent>.md or .claude/skills/<skill-name>/SKILL.md in the files. This feels like dependencies that leak from outside this repository. My preference is that the repo is self contained. What I want here is to check out the dev-team repo, add the command to run the python entrypoint or the TUI runner as an alias, then in the directory (initially an empty git repo checked out somewhere), I type the aliased command in, the TUI starts in the current directory and it's ready to go. It should have the same behaviour, agents, skills etc on whichever computer I check it out on.

> Note, this is part of specifying the final dev-team product so I'm not expecting the changes to be implemented, just captured in the appropriate story.

Captured in [STORY-006](stories/STORY-006.md).

## Customer simplification: step in front matter, workflow in JSON

Captured 2026-10-04. Where this differs from the earlier messages, this wins.

> The front matter is looking very busy and more sophisticated than I want it to be. The intent is a work item has a workflow, the workflow is defined in JSON and specifies the owner of each step and what valid transitions exist. The work item has it's current step in the front matter. The python script parses the front matter to determine whether it's for a human to action, or an agent. If it's an agent, it follows the config for what agent and model to invoke with the work item details. The other part is a terminal UI to show the human what work items there are, what step they are in and give the human a way of interacting / answering questions and moving the work item into one of the defined valid steps. It feels like this happy path is already getting lost.

> rewrite the backlog, drop depends_on and remove the story 2/3 code

Consequences: the backlog was rewritten as five epics and a handful of stories; the
`depends_on` field was dropped; the persistence protocol (former STORY-002) and
legacy import (former STORY-003) were removed from the code. Front matter is
`id`, `type`, `title`, `parent`, `workflow` and `step`.

## Customer clarification: it starts with a request for analysis

Captured 2026-10-04.

> This isn't purely about managing stories that exist. This should start with me as the customer entering an initial brief and having the dev team interview me to get all the details. This could be well defined in the workflow json still, as an analysis / backlog capture part of the flow. I don't know if this would need an additional work-item type, or if it would just end up in an epic?

> A brief is almost always going to be an initial idea. The idea will evolve over time with new features not initially in the brief, changes in audience and design will occur incrementally. The output of the analysis steps is epics / stories / tasks / bugs. I guess it needs some kind of name, but brief feels too big a concept. For the analysis, I quite like the idea the product owner analysis can move the analysis request to a different agent for their input, or back to the human for questions, or move it to analysis complete. Each role has their own analysis step and ask human questions step. For roles that aren't product owner, they can't move it to analysis complete, they can only pass it back to the product owner to decide.

Captured in [STORY-005](stories/STORY-005.md) as a `request` work-item type with
its own analysis workflow.
