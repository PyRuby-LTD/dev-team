# 06: Default workflow group 1 - analysis, challenge and ready

**What to build:** A story at `captured` goes through analysis with questions and answers, then challenge; challenge findings that would change what is built send it back to analysis with the findings as pending input; a sound story waits at `ready`, where the customer can `rework` with feedback. The analysis and challenge prompts are drafted as Jinja templates from the role briefs, standards and the author's development notes, for the author to review.

**Blocked by:** 01

**Status:** ready-for-agent

- [x] A journey test takes a story from `captured` through analysis, a question and answer, challenge with a `rework`, analysis again, challenge `sound`, to `ready`, asserting on requirements and step history
- [x] The findings from challenge appear in the analysis step's pending input on the second run
- [x] Analysis and challenge prompts are drafted and previewable from the command line, flagged for the author's review

## Comments

`prompts/analysis.md` and `prompts/challenge.md` are redrafted for YAML items from the product owner and challenger briefs, the standards and `Development patterns.md`. They need the author's review; preview them with `uv run python -m devteam prompt analysis` and `... prompt challenge`. Points to settle while reviewing:

- The notes name the other personas a story affects in its Testing ACs; the prompts use `personas_affected`, as the work-item example does.
- The challenger judges "decisions the customer did not make" from the answers and feedback only: a story's text as first captured is not kept anywhere once analysis revises it.
- `test_questions.Parsing.test_analysis_prompts_discourage_placeholders` asserts the original Markdown wording that `prompts/analysis.md` no longer carries; it already failed for `prompts/analysis/product-owner.md`, and goes with the original harness in issue 13.
