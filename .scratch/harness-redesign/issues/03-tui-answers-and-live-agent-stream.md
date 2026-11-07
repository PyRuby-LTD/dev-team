# 03: The TUI answers questions and streams a running agent

**What to build:** When an item at a customer step has unanswered questions, the TUI shows each question with a free-text answer box below it before the customer chooses an outcome, since the questions may change which outcome they choose. Every question needs an answer; the customer writes n/a for one they will not answer. Answers stay attached to their questions across rounds. While an agent runs, the TUI shows its live stream. This completes milestone 1: a request goes back and forth with the customer through questions and answers in the TUI and ends with drafted work items as valid YAML in the backlog.

**Blocked by:** 02

**Status:** ready-for-agent

- [x] A pilot test answers a request's questions before choosing its outcome, is refused while one is blank, and finds the answers on the right questions in the work item
- [x] A pilot test sees a stub agent's streamed output reach the TUI while it runs, without asserting on its wording
- [ ] The milestone 1 demonstration works by hand against a real product owner: capture, analyse, answer, draft, approve
