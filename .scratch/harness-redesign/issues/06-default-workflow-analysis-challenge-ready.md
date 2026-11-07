# 06: Default workflow group 1 - analysis, challenge and ready

**What to build:** A story at `captured` goes through analysis with questions and answers, then challenge; challenge findings that would change what is built send it back to analysis with the findings as pending input; a sound story waits at `ready`, where the customer can `rework` with feedback. The analysis and challenge prompts are drafted as Jinja templates from the role briefs, standards and the author's development notes, for the author to review.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] A journey test takes a story from `captured` through analysis, a question and answer, challenge with a `rework`, analysis again, challenge `sound`, to `ready`, asserting on requirements and step history
- [ ] The findings from challenge appear in the analysis step's pending input on the second run
- [ ] Analysis and challenge prompts are drafted and previewable from the command line, flagged for the author's review
