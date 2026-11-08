# dev-team

A product delivery team defined as roles and workflows: the harness moves work items through workflow steps, and the roles and the customer own those steps.

## Language

**Harness**:
The program that interprets workflows, hands each step to its owner, and records each step's outcome and output on the work item. It knows nothing role-specific.
_Avoid_: Runner (for the whole), engine, orchestrator

**Workflow**:
A named set of steps, each with an owner and outcomes leading to other steps, that a work item follows from its initial step.
_Avoid_: Pipeline, process

**Step**:
One stage of a workflow, owned by exactly one owner, with its outcomes and the shape of output it accepts.
_Avoid_: Stage, state, status

**Owner**:
Who performs a step: the customer, an agent role, or the harness itself.
_Avoid_: Assignee, actor

**Harness step**:
A step the harness performs itself, such as syncing a branch or running the project's check.
_Avoid_: Action, automatic step

**Outcome**:
The named result of a step, which decides the next step.
_Avoid_: Transition, result, decision

**Output**:
What a step produces for the work item, checked against the shape the step declares.
_Avoid_: Fragment, payload

**Feedback**:
Free text the customer leaves with an outcome, addressed to the owner of the step it leads to.
_Avoid_: Note, comment

**Submission**:
An agent's call to the harness with an outcome and output for its step; checked when made, recorded once the agent exits.
_Avoid_: Reply, response

**Work item**:
A request, epic, story, task or bug, holding its requirements and the history of the steps it has been through.
_Avoid_: Ticket, record, issue

**Request**:
A work item describing what the customer wants at the level of the idea, which analysis divides into other work items.
_Avoid_: Idea, brief

**Role**:
An agent persona that owns steps, such as the product owner or the implementer.
_Avoid_: Agent (for the persona), persona

**Role brief**:
What a role believes and values, written in the team author's own words.
_Avoid_: System prompt, persona file

**Standard**:
A rule of good practice, in the team author's own words, that analysis chooses for an item and review enforces.
_Avoid_: Guideline, policy

**Prompt**:
The task a role is given for one step, rendered from a template with the work item and step.
_Avoid_: Instructions, brief

**Checkout**:
The product repository's single working tree, which only one item's work may hold at a time.
_Avoid_: Workspace, repo

**Item branch**:
The branch in the checkout where one work item's code changes are made.
_Avoid_: Feature branch, story branch

**Customer**:
The human who says what is wanted, answers questions, and makes the decisions only they can make, such as playing an item or accepting a change.
_Avoid_: User, human
