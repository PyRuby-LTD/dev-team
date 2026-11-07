# Spec: The redesigned harness replaces the original

Status: ready-for-agent

## Problem Statement

The original dev-team harness knows too much. Its runner, terminal UI and Markdown backlog each carry role-specific knowledge: how questions and answers sit in an item body, how pull request feedback is copied in, how evidence and publication bodies are laid out. Every change to a role or a workflow tends to need a change in the harness too.

A redesign is under way on the `redesign` branch: YAML work items with requirements at the root and a step history, workflow definitions in YAML whose steps declare their owner, outcomes and output shape, step classes per kind of owner, Jinja2 prompts, and agent submissions that the harness validates. But the redesign still leans on the original runner for every step's work, has no terminal UI of its own, and covers none of branch handling, concurrency or the later default-workflow steps. The distance between "taking shape" and "replaces the original" is large enough that the work has stalled.

## Solution

Finish the redesign on the `redesign` branch until it fully replaces the original harness, then merge it to main with a pull request.

The finished harness interprets workflow YAML, hands each step to its owner, accepts submissions from agents, validates and records each step's outcome and output, and moves the work item to the next step. Everything role-specific lives in workflow definitions, role briefs, standards and prompts. The customer drives it through a rebuilt terminal UI that keeps the interactions that matter: choosing an outcome from a list, answering an agent's questions in free text, leaving feedback for the next step's owner, capturing a new request, and later choosing standards for an item about to be played.

The work proceeds in five milestones:

1. The request workflow runs end to end in the new TUI: a request goes back and forth between the product owner and the customer through questions and answers, and ends with drafted work items as valid YAML in `backlog/`.
2. Each item's code work happens on its own item branch, with a queue for the checkout, one agent run at a time.
3. The default workflow comes online in groups of steps, each group bringing its prompts.
4. Agents that do not hold the checkout run concurrently.
5. The remaining original code is deleted and a pull request merges `redesign` into main.

## User Stories

### Capturing and analysing a request

1. As a customer, I want to capture a new request in the TUI as free text, so that I can describe an idea without knowing the work-item format.
2. As a customer, I want a captured request to sit at its initial step until I choose to have it analysed, so that nothing runs before I am ready.
3. As a customer, I want to choose `analyse` from a list of the step's outcomes, each shown with what it means, so that I know what each choice will do.
4. As a customer, I want the product owner to be invoked as soon as I choose `analyse`, so that analysis starts without a separate command.
5. As a customer, I want to watch the product owner's live output in the TUI while it analyses, so that I can judge how well the new prompts work.
6. As a customer, I want the product owner's questions put to me, each with a free-text answer box below it, before I choose the step's outcome, so that the answers can shape which outcome I choose.
7. As a customer, I want to answer a question I cannot or will not answer with n/a, so that every question has an answer and none is silently skipped.
8. As a customer, I want my answers to stay attached to their questions across rounds of analysis, so that none are lost or reordered.
9. As a product owner agent, I want my earlier questions and the customer's answers in my prompt, so that I build on them instead of asking again.
10. As a product owner agent, I want to create each drafted work item through the harness command while analysing a request, so that every draft is a valid YAML work item from the start.
11. As a product owner agent, I want my submission rejected at once with the reasons when its outcome or output is invalid, so that I can fix it and submit again before I exit.
12. As a product owner agent, I want my last valid submission to be the one recorded, so that I can correct myself without side effects.
13. As a customer, I want to review a request's drafted items before approving it, so that I can see how the work was divided.
14. As a customer, I want to choose `revise` with feedback on a request, so that the product owner reworks the drafts with my reasons in front of it.
15. As a product owner agent, I want feedback from the customer addressed to my step in my prompt, so that I act on it.
16. As a product owner agent revising a request, I want to update existing drafts and take unneeded ones out of the request's work items, explaining why, so that the customer can mark them won't fix.
17. As a customer, I want approved drafts to wait at `captured` in their own workflow, so that I decide which to play and when.
18. As a customer, I want every drafted item to be a valid YAML document in the backlog directory, so that I can read, diff and version it.
19. As a customer, I want the request to list the items it was divided into, so that I can trace each draft back to its request.

### Viewing work items

20. As a customer, I want the TUI to list every YAML work item with its step and who that step is waiting on, so that I see where everything stands.
21. As a customer, I want items grouped under their epic, so that I see a body of work together.
22. As a customer, I want to filter to the items waiting on me, so that I know what needs my attention.
23. As a customer, I want an invalid work-item file listed with its error while the rest of the backlog still loads, so that one bad file does not hide everything.
24. As a customer, I want the TUI to ignore the original Markdown items, so that I can triage them by hand without them cluttering the new backlog.
25. As a customer, I want an item's detail view to show its requirements and the step outputs waiting on its current step, so that I have what I need to decide.
26. As the team's author, I want the detail view rendered from a template, so that changing what is displayed is a template edit, not a code change.

### Workflows as the source of behaviour

27. As the team's author, I want to change a step's owner, outcomes or output shape in workflow YAML and see the harness and TUI follow without a code change, so that the workflow is the single source of behaviour.
28. As the team's author, I want an invalid workflow reported clearly when it loads, naming the step and problem, so that I can fix it before anything runs.
29. As the team's author, I want a workflow that asks the TUI for a customer input it does not know rejected at load time, so that a workflow cannot silently ask for something nobody can enter.
30. As the team's author, I want to preview the prompt any agent step would be given for an item, from the command line, so that I can review prompts without running an agent.
31. As the team's author, I want role briefs and standards to stay in my own words, with prompts as templates I review, so that the team carries my voice.

### Branches and the checkout

32. As a customer, I want each item's code work done on its own item branch in the checkout, so that items do not mix their changes.
33. As a customer, I want only one item's work to hold the checkout at a time, with others queued, so that agents never trample each other's working tree.
34. As a customer, I want to see in the TUI when an item is waiting for the checkout, so that I know why it has not started.
35. As a customer, I want the backlog kept on its own branch as before, so that work-item changes never mix with product code.
36. As a customer, I want machine paths kept out of everything committed to the backlog, so that my home directory and tooling layout do not leak.

### The default workflow

37. As a customer, I want a story drafted by a request to go through analysis with questions and answers, then challenge, then wait at `ready`, so that it is specified before anything is built.
38. As a customer, I want to see the standards analysis chose for an item at `ready`, each with its reason, as a checklist, so that I can confirm or override them before playing it.
39. As a customer, I want to add a standard analysis missed when playing an item, so that, for example, a UI story follows the reusable component library standard.
40. As an implementer, tester or reviewer agent, I want the item's chosen standards in my prompt, so that I build, test and judge against them.
41. As a customer, I want to choose `play` with optional feedback, so that the implementer starts with any steer I give.
42. As an implementer agent, I want my submission to record the branch, libraries added, tech tasks, surprises and opinions, so that the customer and later steps can see them.
43. As a customer, I want the tester to write or extend journey tests and report defects back to the implementer, so that the change is proven.
44. As a customer, I want the item branch to merge its base, and an agent to resolve conflicts when it does not merge cleanly, so that the change stays current.
45. As a customer, I want the project's own check run on the branch, sending the item back on failure, so that I trust what reaches review.
46. As a customer, I want the reviewer's findings recorded as fix or task, and the item sent back when a criterion is unmet, so that review has teeth.
47. As a customer, I want to accept a change, revise it with feedback, or abandon it at `accept`, so that nothing is published without my say.
48. As a customer, I want accepted work synced, checked and published as a pull request, so that it reaches the product the usual way.
49. As a customer, I want a rejected pull request's feedback recorded on the item for the implementer, so that rework addresses it.
50. As a customer, I want a merged pull request to bring the base branch up to date and finish the item, so that the backlog reflects reality.
51. As a customer, I want abandoning an item to return the checkout to the base branch while keeping the item branch, so that I can recover the work later.
52. As a customer, I want to mark an item won't fix from `captured` or `ready`, keeping it as a record, so that dropped drafts and abandoned ideas are never deleted.

### Concurrency

53. As a customer, I want agents that do not need the checkout, such as request analysis, to run while another item holds it, so that analysis is not stuck behind implementation.
54. As a customer, I want several items' non-checkout steps to run in parallel, so that the team is not limited to one agent at a time.

### Running the harness

55. As a customer, I want to launch dev-team from any product directory and have it act on that product's backlog while using the harness's own workflows, prompts, briefs and configuration, so that it behaves the same for every product.
56. As a customer, I want a missing engine command or an engine exiting with an error reported, with the item left at its step, so that a failure never moves work on.
57. As a customer, I want an agent that exits without a valid submission to leave the item at its step with the reason shown, so that I can see what went wrong and retry.
58. As a customer, I want each role's engine and model to come from the roles configuration, so that I can switch a role between engines without touching workflows.
59. As a customer, I want each agent run's transcript kept under the item's log, so that I can read back what an agent did.
60. As a customer, I want the product's setup (a backlog branch and a regression target) to be a prerequisite checked at launch, so that workflows never start in a product that cannot run them.

## Implementation Decisions

### The harness

- The harness's whole job is one loop: find an item whose current step the harness or an agent owns, ask the step to perform, then validate, record and move the item on by the outcome. Recording and moving on happen only in this loop, never inside a step.
- Every step's perform returns an outcome and an output, or says it is waiting to be tried later. Steps no longer call the original runner to apply transitions.
- An agent step performs by rendering its prompt, running its role's engine, and taking the staged submission once the agent exits. No valid submission means the item stays at its step with the reason reported.
- A harness step (sync, check, merged, abandon, pull request, rejected) performs its git or check action and returns the outcome. The original runner's actions move behind these step classes, keeping only what each step needs.
- A customer step is never performed by the harness. The TUI records its outcome and output through the same validation that agent submissions go through.
- `Rejected` stops editing a Markdown body: the pull request's feedback becomes its step output, addressed to the implementer.
- Agents talk to the harness only through the `dev-team backlog` commands: submit (outcome plus output on stdin), create and update. Submit validates at once and stages; the loop records after the agent exits.

### Original modules

- Nothing from the original harness carries over by default; each piece earns its place behind a step that uses it.
- Engine invocation is how an agent step performs. The roles configuration keeps mapping each role to its engine and model.
- Git operations live behind the git harness steps and the checkout queue.
- The project check lives behind the check harness step.
- Stream rendering stays for the TUI's live agent output.
- Path masking stays as a concern of every backlog write, not a step.
- Product initialisation is a prerequisite of the harness, checked at launch, not a workflow step.
- The original Markdown backlog, JSON workflows, question parsing, publication body, runner and TUI are deleted once nothing on the branch uses them.
- The three role lens prompts (architect, platform engineer, quality lead) are deleted; request analysis is a single product owner step that applies those lenses through standards.
- On the `redesign` branch, the new harness takes over the `dev-team` entry point from milestone 1; there is no second entry point.

### Work items and backlog

- The new harness reads only `.yaml` work items in the backlog directories. Original `.md` items are left untouched for the customer to triage by hand and bring back through new requests. There is no converter.
- An item's requirements sit at its root; every run of every step appends an entry to its step history, addressed to the step it leads to. Entries addressed to the current step and not yet taken are the step's pending input. This model is already in place and is kept.
- Feedback is a free-text output field on customer steps. It reaches the next step's owner as pending input; no other mechanism carries it.
- Questions merge by their text so answers stay attached across rounds. This is kept.
- The default workflow gains a terminal `wontfix` step, reached from `captured` and `ready` by a customer outcome. Nothing is ever deleted from the backlog.
- A product owner revising a request updates existing drafts with the update command and takes unneeded drafts out of the request's work items with a reason. It does not close them; the customer marks them won't fix.

### Customer inputs in the TUI

- The TUI is rebuilt rather than ported. The original TUI is a reference for interactions, not a starting point.
- The TUI knows exactly five kinds of customer input:
  1. Choose an outcome from the current step's list, each shown with its meaning.
  2. Answer questions: each unanswered question with a free-text box below it, offered before the outcome and each requiring an answer.
  3. Feedback: a free-text box when the step's output has a `feedback` field.
  4. New request: free text that captures a request.
  5. Standards: a checklist of available standards, pre-ticked with the item's chosen standards and their reasons (milestone 3).
- Any other output field on a customer step is rejected when the workflow loads.
- Standalone notes to an agent, without choosing an outcome, are dropped.
- The detail view is a Jinja template rendered with the same environment as prompts (same filters) and shown as Markdown. Its context matches a prompt's: the item, its current step, the workflow, and the step's pending input.
- The TUI shows a running agent's live stream.

### Standards at `ready`

- The customer's choice of standards at `ready` replaces the item's `standards` requirement, so the implementer, tester and reviewer all see it. A standard the customer adds gets the reason "chosen by the customer".
- `ready` therefore writes the `standards` requirement field as well as recording feedback. This is the only customer step that writes a requirement field other than answers.

### Branches and concurrency

- Whether a step holds the checkout comes from the step: git and check steps hold it, and an agent step holds it when its role works on a branch (per the roles configuration).
- Milestone 2 runs one agent at a time with a queue for the checkout and an item branch per item. Milestone 4 lets steps that do not hold the checkout run concurrently with the one that does.

### Prompts, briefs and standards

- Role briefs and standards are written by the team's author. Tickets touching them are for a human.
- Prompts are Jinja templates drafted by agents from the briefs, standards and the author's development notes, for the author to review. Each milestone-3 group brings the prompts for the steps it brings online.

## Testing Decisions

- A good test drives the harness from outside and asserts on what it leaves behind: the YAML work items in the backlog directory, their step and step history, and the git commits. Tests never assert on displayed or prompt wording.
- The seam is the `dev-team` command run as a subprocess against a temporary product git repository, with stub `claude`, `codex` and `gh` CLIs on the path. The stubs follow a scripted plan in which each run calls `dev-team backlog submit` or `create` exactly as a real agent would.
- One test is one journey, for example: capture a request, analyse it into a question, answer it, analyse into drafts, approve, and find valid drafts at `captured`. Later journeys cover branches and the checkout queue, each default-workflow group, won't fix, standards at `ready`, and concurrency.
- Failure journeys run through the same seam: an invalid submission is refused with reasons, an agent exiting without a submission leaves the item in place, a missing or failing engine is reported, an invalid workflow is reported at load.
- Customer steps are exercised at the command seam through the same commands the TUI calls, so the journeys cover recording customer outcomes, answers, feedback and standards without driving the TUI.
- The TUI is tested lightly: a small number of pilot tests that it opens on a backlog and that each of the five inputs reaches the harness. No assertions on labels or layout.
- The existing module-level tests of the redesign are kept only where a behaviour is hard to reach through the command seam, such as requirement merging edge cases, and removed as journeys cover them.
- Prior art: the launcher tests that run the command as a subprocess against temporary products with stub engines; the scripted engine stub that follows a plan per invocation; the original TUI's pilot tests for the light TUI coverage.

## Out of Scope

- Moving the TUI's knowledge of questions and answers into the workflow YAML. A worthwhile spike, but later.
- Product initialisation as a workflow step, such as a walking-skeleton workflow.
- Converting original Markdown items to YAML.
- Schema-driven forms for customer outputs beyond the five known inputs.
- Standalone notes to an agent outside choosing an outcome.
- Separate architect, platform and quality agents during analysis.

## Further Notes

- Main keeps the original harness, which stays usable on product work throughout. The `redesign` branch is free to be broken for the default workflow while milestone 1 works.
- Milestone 1 cannot be judged until the TUI works, so the harness loop and the TUI arrive together for the request workflow.
- The redesign is not complete until customers can choose standards at `ready`, even though that arrives late.
- `Development patterns.md` holds the author's notes on what they value; it is source material for briefs and prompts, not a record of decisions.
