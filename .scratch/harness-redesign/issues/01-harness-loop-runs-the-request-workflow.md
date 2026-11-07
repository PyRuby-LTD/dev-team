# 01: The harness loop runs the request workflow from the command line

**What to build:** On the `redesign` branch, `dev-team` runs the new harness. A customer captures a request and records customer outcomes from the command line; the harness loop hands agent steps to their role's engine (from the roles configuration). The agent is prompted to call `dev-team backlog submit` with its outcome and YAML output; each call is checked at once against the step's outcomes and output shape, and the agent is told what is wrong so it can fix it and submit again. After the agent exits, the loop records the last valid submission and moves the item to the next step. Every step's perform returns an outcome and output (or says it is waiting); only the loop records and moves items on, so steps no longer call the original runner to apply transitions. Customer outcomes, with their output, are recorded through a command that the TUI will reuse, validated the same way as submissions.

See the spec: `.scratch/harness-redesign/spec.md` (The harness; Testing Decisions).

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] A journey test at the command seam (subprocess against a temporary product repo, stub engines on the path following a scripted plan) captures a request, analyses it into a question, records the customer's answer, analyses it into drafts created through `dev-team backlog create`, approves it, and finds each draft as a valid YAML work item at `captured` and listed in the request's work items
- [ ] In that journey a stub agent's first submission is invalid (unknown outcome or output that does not fit), it receives the reasons from the command, and its corrected second submission is the one recorded
- [ ] An agent that exits with nothing staged leaves the item at its step, with the reason reported
- [ ] A missing engine command, or an engine exiting non-zero, is reported and the item stays at its step
- [ ] An invalid workflow is reported at load, naming the step and the problem
- [ ] Recording a customer outcome with invalid output is refused with reasons, leaving the item unchanged
- [ ] Original modules this supersedes on the branch are deleted, along with their tests
