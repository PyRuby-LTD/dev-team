---
id: STORY-022
type: story
title: Fold decisions into acceptance criteria in prompts
parent: EPIC-001
workflow: default
step: publish
---
As a customer, I want the statement, Context and Acceptance Criteria to be revised as decisions are made, so that an implementer and tester have everything they need to build and verify the story without the discussion that led to it.

## Context

REQUEST-006. Only Context and Acceptance Criteria survive to `docs/work-items/<id>.md`, so Questions, Feedback and Response sections are not kept. As with a typical dev team, the outcome of those conversations should evolve the story and update the criteria; the discussion itself is not kept. Where the reason for a change matters to implementation or test, it is included in the criteria or Context.

Scope boundary: only decisions made before implementation starts (questions, challenge, and feedback at analysis) are folded in. Feedback at `accept`, `review` or on a rejected pull request should concern the quality or treatment of what was built, not new scope; new scope belongs in a separate story so that the product owner and architect see it. Such late feedback is therefore not written back into the published criteria.

What changes: only prose. The analyst prompt `prompts/analysis.md`, the product owner prompt `prompts/analysis/product-owner.md` and the briefs `roles/analyst.md` and `roles/product_owner.md`. These are the only roles that revise requirements. The architect, platform engineer, quality lead and challenger only add working sections, so their prompts are unchanged, as is `prompts/implement.md`. No workflow step, transition or code changes.

Requests are never published (the analysis workflow has no publisher step; only the publisher role records to `docs/work-items/`). The product owner's request body stays a working document. The new instruction applies to the stories, bugs and tasks the product owner captures, not to the request.

STORY-021 defines what is published (the preamble, `## Context`, `## Acceptance Criteria`). The prompts here must not depend on whether that filter has shipped, so they state the rule as "these are the requirements" and not as "other sections are dropped". Heading names must match STORY-021. `tests/test_questions.py` already reads prompts from disk and asserts on their wording, as a pointer for how wording is checked today.

The statement may be revised by the analyst and, as an assumption (the customer only named the analyst), by the product owner who writes it at capture and revises on `revise`. The implementer, tester and reviewer do not revise it. Original request text the customer wrote is left as written.

## Analysis

Findings against the repository:

- No role prompt mentions the kept sections today. `prompts/analysis.md` (analyst) says to "record your findings in the item body, and add or tighten the acceptance criteria"; `prompts/analysis/product-owner.md` says to preserve answers and findings in the request body and to include acceptance criteria "reflecting the answers and specialist findings" in each captured item. Nothing says a decision should change what the story specifies, so answers and feedback currently stay only in working sections.
- The roles that revise requirements are the analyst (stories, bugs, tasks, on `analysis`, including after a challenge or customer feedback) and the product owner (requests, including `revise`). The architect, platform engineer and quality lead only add findings for the product owner; the challenger only adds a `## Challenge` section. Their prompts need no change. The briefs `roles/analyst.md` and `roles/product_owner.md` carry the same duties.
- The publish filter does not exist yet. The copy in `docs/work-items/` is written by the `role.record` block in `Runner.invoke` (`devteam/runner.py`) and today holds the whole body. STORY-021 adds the filter: front matter, the preamble (the statement and original request), `## Context` and `## Acceptance Criteria`. This story needs no code from it, but the heading names in the prompts must match it.
- Requests are never published. `workflows/analysis.json` has no publisher step, and in `config/roles.toml` only the publisher has `record = true`. The product owner's own request body (`## Product owner findings`, `## Questions` and so on) is a working document and stays as the prompt says today. Only the stories, bugs and tasks the product owner captures reach `docs/work-items/`, so the new instruction applies to those bodies, not to the request.
- Late feedback: `accept` and `review` revise, and `pull-request` rejected (via `runner.rejected`, which writes `## Pull request feedback`), all go to `implement`. `prompts/implement.md` acts on `## Feedback` and `## Pull request feedback` and never mentions the criteria. Only the publisher has `record = true`, so the published copy is written after these loops. The customer answered question 1: late feedback is not folded into the criteria, so this is a deliberate boundary and not a gap.
- `tests/test_questions.py:94` already reads the analysis prompts from disk and asserts on their wording, so a prompt-content test has a precedent.

The "As a ... I want ... so that ..." statement is normally written by the product owner at capture, not by the customer. The customer (question 2) said changes to the statement are made before the implementation step and that the analyst can update it. This is read as a rule about role and step, not time: the analyst (and, as an assumption, the product owner) may revise it; the implementer, tester and reviewer may not. The workflow can send a blocked item back to analysis after implementation has begun, and the analyst then revises Context and criteria and the statement in the same way, so no "has implementation started" test is needed. The challenger's point that the analyst cannot tell when implementation started is accepted.

First-pass findings are not decisions but are covered too: `## Analysis` is a working section, and anything in it that the implementer or tester needs (what exists, what changes, where the precedents are) goes into Context or the criteria. Findings are not published as `## Analysis`. Original request text the customer wrote is left as written. This item's own statement has been revised accordingly, since it overstated questions and feedback.

Intent (customer feedback): the statement, Context and Acceptance Criteria must give the implementer and tester everything needed to build and verify the story. Questions, answers, feedback and challenge text must not appear verbatim in the criteria; only their effect on what is built, and anything the tester needs to verify it, goes in.

## Acceptance Criteria

1. The analyst prompt (`prompts/analysis.md`) tells the analyst that `## Context` and `## Acceptance Criteria` must give an implementer and tester working only from the statement and those two sections everything they need to build and verify the story. This covers the analyst's own findings from investigating the repository (which stay in `## Analysis` as a working record) as well as the effect of answered questions, feedback received and challenges addressed. It is done on every pass through analysis, including a rework.
2. The product owner prompt (`prompts/analysis/product-owner.md`) gives the same instruction for the stories, bugs and tasks it captures or revises, so their Context and criteria already reflect the answers and specialist findings. It does not apply to the request body, which remains a working document where the product owner keeps the customer's text, findings and answers as today.
3. Both prompts say what to fold in and what to leave out: what a decision changes about what is built, and any information the tester needs to verify it, go into Context or the criteria; question, answer, feedback or challenge wording is not copied or quoted into them; a reason for a change is included only when the implementer or tester needs it.
4. Both prompts state that, for a story, bug or task, only the statement, `## Context` and `## Acceptance Criteria` are the requirements, and that nothing an implementer or tester needs may exist only in other sections such as `## Analysis`, `## Questions`, `## Feedback` or `## Challenge`. The wording must hold whether or not STORY-021's publish filter has shipped.
5. The only published sections the prompts name are `Context` and `Acceptance Criteria` (plus the statement), matching the kept parts in STORY-021. The prompts still name working sections such as `## Questions` and `## Challenge`, as criterion 7 requires.
6. Both prompts say what may be changed in the text above the first `##` heading, which STORY-021 publishes as the preamble: the "As a ... I want ... so that ..." statement may be revised by the analyst or product owner when a decision changes what the story is about, and not by the implementer, tester or reviewer; any original request text the customer wrote is left as written. The prompts do not call the statement the customer's words.
7. No prompt change alters workflow steps, transition names, the `## Questions` format (numbered list, `**Answer:**` lines) or the section names agents use to hand over between steps. The briefs `roles/analyst.md` and `roles/product_owner.md` carry a short statement of the same principle; the architect, platform engineer, quality lead and challenger prompts are unchanged.
8. The analyst and product owner prompts contain one identical sentence (whitespace aside) covering: whatever the implementer and tester need, from findings or decisions, goes into `Context` and `Acceptance Criteria`; the statement may be revised by the analyst or product owner and original request text is left as written, per criterion 6; and nothing needed may exist only in other sections. It says "a story, bug or task" rather than "this item", so it reads correctly in both prompts. The implementer chooses the wording.
9. Feedback given after implementation (at `accept`, `review`, or on a rejected pull request) does not update the statement, Context or Acceptance Criteria. `prompts/implement.md` is unchanged. The boundary is recorded in this item's Context; nothing further is built for it.

## Questions

1. Decisions can also arrive after analysis: feedback at `accept` or `review` (which return to `implement`), and comments on a rejected pull request. The implementer prompt tells it to act on these but not to update the criteria, and the published copy is written after those loops, so a late decision such as "also handle X" would appear only in sections that are not published. Should such late decisions also be written into the statement, Context and Acceptance Criteria? If yes, should the implementer do it (a change to `prompts/implement.md`), or should the item go back through analysis? If no, we will state in Context that the published criteria cover decisions made up to the start of implementation.

   **Answer:** This is an interesting challenge, because feedback at accept and review stage should be about the implemented story, not about adding scope. I am tempted to go with not updating the ACs or context at that point. It should either be a visual treatment type issue, or code quality etc. Additional criteria at that point should really be a separate story and adding it here bypasses the product owner, architect etc input.

2. The "As a ... I want ... so that ..." statement is normally written by the product owner when the item is captured, not by you. May the analyst and product owner revise that statement when a decision or your feedback changes what the story is about (for example, this story's own statement still stresses questions and feedback)? Text you wrote yourself, such as an original request, would stay as written either way. If the statement must not be revised, who, if anyone, may change it?

   **Answer:** Any changes to the statement should be made prior to the implementation step. The analyst can update it.

## Feedback

- **analyse -> analysis:** This story has the wrong focus, stressing the questions and feedback too specifically. The intention here is that between the initial "As a <person> I want <thing> so that <result>" and the list of acceptance criteria, the implementer and tester have the information they need to implement and test the story. What I do NOT want is to see the questions, answers and feedback appearing in the acceptance criteria verbatim. Only update the acceptance criteria to reflect how that feedback affects what is being built and any information the tester may need to verify the implementation meets those acceptance criteria.

## Challenge

Verdict: sound. A competent engineer could change the two prompts and two briefs as written, and a reviewer could tell from the criteria whether they had. All four earlier findings are addressed. Criterion 1 now covers the analyst's own findings as well as decisions. The statement rule is tied to role and step, and the product owner's part is stated as an assumption in Context. Criterion 4 holds whether or not STORY-021 has shipped. Criterion 8 states an observable requirement (one identical sentence) without prescribing the test.

Claims checked against the repository and found to hold:

- `prompts/analysis.md`, `prompts/analysis/product-owner.md`, `roles/analyst.md` and `roles/product_owner.md` say what the Analysis quotes.
- `config/roles.toml` gives `record = true` only to the publisher.
- `workflows/analysis.json` has no publisher step, so requests are never published.
- `workflows/default.json` sends `accept` and `review` revise, and `rejected`, back to `implement`. The path `implement --blocked--> ready --rework--> analysis` exists as the Analysis describes.
- `tests/test_questions.py:94` asserts a shared sentence across all five analysis prompts, and criterion 7 leaves that sentence intact.

Minor points, none of which changes what gets built:

1. Criterion 5 says "the only published sections the prompts name", while criterion 4 asks for wording that does not depend on publishing. Read together, they mean the prompts name `Context` and `Acceptance Criteria` (plus the statement) as the requirements. Saying "requirement sections" in criterion 5 would stop an implementer reading it as licence to describe what is published.
2. STORY-021 criterion 4 lists requests among the published types. That contradicts this item's verified finding that requests are never published. It does not affect this story, but whoever analyses STORY-021 should be told.

This challenge only read files and ran no checks, so there is no command output to save.

## Implementation

Implemented the prose changes in `prompts/analysis.md`,
`prompts/analysis/product-owner.md`, `roles/analyst.md` and
`roles/product_owner.md`. Both prompts now require self-contained requirements
on every analysis/capture/revision pass, explain how findings and decisions
affect the work without quoting discussion, and share an identical sentence
covering requirements, statement revision and preservation of original customer
text. The product owner rule applies to captured stories, bugs and tasks; the
request remains a working document. The briefs state the same principle.

Workflow steps, transitions, question formatting, specialist and challenger
prompts, and `prompts/implement.md` are unchanged. The late-feedback boundary
remains in Context as specified; no implementation behaviour was added for it.

Acceptance criterion coverage:

1. No new unit test: analyst prompt prose, left to human judgement at review.
   It covers repository findings in the Analysis working record, answered
   questions, feedback and challenges on every pass, including rework.
2. No new unit test: product owner prompt prose, left to human judgement at
   review. Capture and revision use the same requirements rule, explicitly
   excluding the request body.
3. No new unit test: wording left to human judgement at review. Both prompts
   distinguish the effect on what is built and verification information from
   verbatim discussion, and include reasons only when needed.
4. No new unit test: wording left to human judgement at review. Both prompts
   define the statement, Context and Acceptance Criteria as the requirements
   and prohibit needed information remaining only in working sections, without
   depending on publication filtering.
5. No new unit test: section naming is prose left to human judgement at review.
   Context and Acceptance Criteria are the only named requirement sections;
   working section names remain available for handover.
6. No new unit test: prose left to human judgement at review. Both prompts
   describe the preamble, permit analyst/product owner statement revision when
   a decision changes the story, exclude implementer/tester/reviewer revision,
   and preserve original customer request text.
7. Existing unit coverage: `tests.test_questions.Parsing.test_analysis_prompts_discourage_placeholders`
   passes and verifies the preserved shared question-format instruction across
   all five analysis prompts. Brief wording and unchanged workflow/other-prompt
   scope were reviewed by diff; no additional tests for prose or unchanged code.
8. No new unit test: prose left to human judgement at review. The identical
   sentence beginning "For a story, bug or task, put everything" is present in
   both prompts with identical line wrapping and covers all required clauses.
9. No new unit test: the boundary is already recorded in Context and the
   implementer prompt is unchanged; no executable change requires testing.

No criterion is deferred to tester journey tests: these are prose changes,
with wording left to human judgement at review under the implementation brief.

Checks and evidence:

- `.venv/bin/python -m unittest tests.test_questions`: passed, 10 tests.
  Output: `backlog/log/STORY-022/unit-tests.log`.
- `dev-team check tests.test_questions`: passed, 10 tests. Harness-saved output:
  `backlog/log/check/20261026T220103700694.log`.
- `uv build --out-dir /tmp/dev-team-story-022-dist`: passed, source distribution
  and wheel built. Output: `backlog/log/STORY-022/build.log`.
- `git diff --check`: passed. Output: `backlog/log/STORY-022/diff-check.log`.
- No separate linter or type-check command is configured in the project.
  The full suite was not run, per the requested targeted-check scope.
- Latest workflow check: none has run yet, as supplied in the work item handoff.

No blockers or check failures.

## Tests

No journey test added: the item changes prompt and brief prose only, with no new user journey, workflow step or code path.

- Left to unit tests: criterion 7 (shared question-format sentence), covered by `tests.test_questions`.
- Left to human judgement at review: criteria 1 to 6 and 8 (prompt and brief wording); criterion 9 is a boundary with nothing built.
- Whole suite passed (366 tests); log: `backlog/log/check/20261026T220147852546.log`.
- Run one test on its own: `dev-team check tests.test_questions`.

## Test run

Run by the harness, 2026-10-26 22:27:24 UTC: passed (exit 0); duration 183.939 seconds.

## Review

Verdict: approve. The diff changes only `prompts/analysis.md`, `prompts/analysis/product-owner.md`, `roles/analyst.md` and `roles/product_owner.md`. Harness run: passed, 366 tests (`backlog/log/STORY-022/verify-20261026T220500012240.log`).

Findings:

1. Minor, no action required. Criterion 8 (one identical sentence in both prompts) is mechanical and could be pinned by a test like the one at `tests/test_questions.py:94`, so later edits cannot drift the two copies apart. I read the two copies in the diff and they are identical, wrapping included. The recorded reason is that prose is left to human judgement. I accept it for this change.
2. Minor, no action required. Each prompt now states the same rule three times: a requirements paragraph, the shared sentence and a "fold in" paragraph. This is redundant but not contradictory.

Criteria:

1. Met. `prompts/analysis.md` says "On every pass through analysis, including rework" that the statement, `## Context` and `## Acceptance Criteria` must be enough to build and verify. It also says repository findings, answers, feedback and challenges are folded in, with `## Analysis` kept as the working record. No test; the recorded reason is prose left to human judgement, accepted.
2. Met. `prompts/analysis/product-owner.md` applies the rule to captured or revised stories, bugs and tasks, including `revise`. It excludes the request body, which stays a working document. No test; recorded reason accepted.
3. Met. Both prompts say to fold in what changes and what the tester needs, not to copy or quote question, answer, feedback or challenge wording, and to give a reason only when needed. No test; recorded reason accepted.
4. Met. Both prompts say only the statement, Context and Acceptance Criteria are the requirements. They say nothing needed may remain only in `## Analysis`, `## Questions`, `## Feedback` or `## Challenge`. Neither prompt mentions publishing or a filter. No test; recorded reason accepted.
5. Met. Only Context and Acceptance Criteria (plus the statement) are named as requirements. Working sections are still named. No test; recorded reason accepted.
6. Met. Both prompts let the analyst or product owner revise the statement when a decision changes the story, and bar the implementer, tester and reviewer. Both leave original customer text as written. Neither calls the statement the customer's words. No test; recorded reason accepted.
7. Met. The diff touches no workflow, transition name, `## Questions` format or other role prompt. Both briefs carry a short statement of the principle. Proven by the unchanged diff scope and by `tests.test_questions` (the shared question-format sentence), which passes in the harness run.
8. Met. The sentence beginning "For a story, bug or task, put everything" is word-for-word identical in both prompts. It covers findings and decisions going into Context and criteria, statement revision, original text left as written and nothing existing only elsewhere. It says "a story, bug or task". No test; recorded reason accepted (see finding 1).
9. Met. `prompts/implement.md` is not in the diff, and the boundary is recorded in Context. Nothing is built for it, so no test is needed.
