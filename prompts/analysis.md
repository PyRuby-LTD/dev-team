Analyse this {{ item.type }} against the repository as it is now, and settle it
into something a competent engineer could build and a tester could verify
without asking anyone. Do not change any files; your output is the item's
requirement fields, submitted below.

Read `README.md`, the glossary and the personas file first, then the code the
{{ item.type }} touches, so you can say how the change alters what the
application does today.

- Keep the customer's own words. Revise the overview only when a decision
  changes what the {{ item.type }} is about.
- Every acceptance criterion comes from the customer: their request, their
  answers or their feedback. What you learn from the code goes in `scope` or
  `context`, never in a criterion you invented.
- Criteria describe the new behaviour in the glossary's terms, not how to
  build or test it, except that a task may name files and functions.
- Add only what was asked for. Where you suspect an edge case, error handling
  or the like is an oversight, ask rather than add it.
- A change to a public API carries its contract fragment in `scope`.
- New terms go in `glossary_changes`, new or changed personas in
  `persona_changes`, and every persona the {{ item.type }} touches in
  `personas_affected`.
- Propose the standards the {{ item.type }} needs from those below, each with
  the reason it applies, in `standards`. Leave out a standard it does not need.

Submit only the fields you change. Nothing the implementer or tester needs may
live only in a question, a finding or feedback: fold its effect into the
requirements.

If you cannot settle the {{ item.type }} without the customer, add one to five
sharp questions to `questions` and choose `questions`. Ask about what you need
to build it, offering the likely answers as options a) ... b) ... ending with
one for something else. Earlier questions and their answers stay in place; do
not answer your own. Assumptions you are comfortable stating are not
questions.
{% if pending | selectattr("output.findings", "defined") | list or pending | selectattr("output.feedback", "defined") | list %}

Each finding and piece of feedback below must be addressed before you choose
`analysed`: change the requirements, or ask the customer when only they can
settle it.
{% endif %}

## The {{ item.type }}: {{ item.title }}

~~~yaml
{{ requirements | yaml }}~~~
{% for entry in pending if entry.output %}

## Sent back by {{ entry.step }} ({{ entry.outcome }})

~~~yaml
{{ entry.output | yaml }}~~~
{% endfor %}

## Standards you can propose
{% include "_available_standards.md" %}
{% set example %}{% include "examples/" ~ item.type ~ ".yaml" ignore missing %}{% endset %}
{% if example %}

## Example {{ item.type }}

The shape and level of detail an analysed {{ item.type }} should reach. Submit only the requirement fields.

~~~yaml
{{ example }}~~~
{% endif %}
