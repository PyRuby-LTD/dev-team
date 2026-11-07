Analyse this work item against the repository you are in. Do not change any
files other than the work item.

Establish whether the item is understood well enough to implement: what exists
today, what would change, and whether its acceptance criteria are concrete and
checkable. Record your findings under `## Analysis`, and add or tighten the
item's `## Acceptance Criteria`.

On every pass through analysis, including rework, revise the requirements so
an implementer and tester working only from the statement, `## Context` and
`## Acceptance Criteria` have everything they need to build and verify the
story, bug or task. Only those parts are the requirements; `## Analysis`
remains a working record of your repository findings.

For a story, bug or task, put everything the implementer and tester need from
findings or decisions into `## Context` and `## Acceptance Criteria`; the
analyst or product owner may revise the statement, leaving original request
text the customer wrote as written, and nothing needed may exist only in
other sections.

Fold in your repository findings and the effect of answered questions,
feedback received and challenges addressed: what changes about what is built
and any information the tester needs to verify it. Do not copy or quote
question, answer, feedback or challenge wording into Context or the criteria.
Include a reason for a change only when the implementer or tester needs it.
Nothing needed may remain only in working sections such as `## Analysis`,
`## Questions`, `## Feedback` or `## Challenge`.

In the text above the first `##` heading, the analyst or product owner may
revise the "As a ... I want ... so that ..." statement when a decision changes
what the story is about; the implementer, tester and reviewer may not revise
it. Leave any original request text the customer wrote as written.

If you cannot proceed without an answer from the customer, add each question as
an item in a numbered list under a `## Questions` heading in the item body and
choose `questions`. The customer's reply appears beneath each question as
`**Answer:** ...`. Leave earlier questions and their answers in place and add
new questions to the end of the list. Assumptions you are comfortable
stating are not questions. Otherwise choose `analysed`; the item then goes to a
challenger before the customer sees it.

If the item has a `## Challenge` section, it was sent back to you. Address each
finding in the item, by changing it or by asking the customer, before choosing
`analysed` again.

Do not write an `**Answer:**` line under a new question; the customer's reply
is added beneath it. Keep one `## Questions` heading and one numbered list
across rounds, with no nested lists, and put findings elsewhere.

## The {{ item.type }}: {{ item.title }}

~~~yaml
{{ requirements | yaml }}~~~
{% for entry in pending if entry.output %}

## Sent back by {{ entry.step }} ({{ entry.outcome }})

~~~yaml
{{ entry.output | yaml }}~~~
{% endfor %}
{% set example %}{% include "examples/" ~ item.type ~ ".yaml" ignore missing %}{% endset %}
{% if example %}

## Example {{ item.type }}

The shape and level of detail a {{ item.type }} should reach. Submit only the requirement fields.

~~~yaml
{{ example }}~~~
{% endif %}
