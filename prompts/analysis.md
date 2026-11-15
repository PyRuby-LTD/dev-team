This is the second pass: settle the detail of this {{ item.type }} now that it
is being played. Do not change any files; your output is the item's requirement
fields, submitted below.

Read `README.md`, the glossary and the personas file, then the code the
{{ item.type }} touches. The code is there so you understand what the
application does today and can find the questions worth asking. Write the
{{ item.type }} for a capable engineer who already knows the codebase: say how
behaviour changes, not where in the code it changes or how to test it.

If you cannot settle the {{ item.type }} without the customer, add your
questions to `questions` and choose `questions`. Earlier questions and their
answers stay in place.

Otherwise submit the fields you change and choose `analysed`:

{% if item.type == "bug" %}
- `current_behaviour`, `expected_behaviour` and `steps_to_reproduce`, precise
  enough that the engineer can reproduce the bug and know when it is fixed.
{% elif item.type == "task" %}
- `context` and `change`, naming the files and functions involved.
- `acceptance_criteria`: how the engineer knows the task is complete.
{% else %}
- `overview`: keep the customer's own words. Revise it only when a decision
  changes what the {{ item.type }} is about.
- `scope`: what the application does today and how this changes it.
- `acceptance_criteria`.
- `personas_affected`: every persona the {{ item.type }} touches.
{% endif %}
- `glossary_changes` and `persona_changes`: revise what the first pass
  recorded and add what this pass found.
- `standards`: each standard below that the {{ item.type }} needs, with the
  reason it applies.

Nothing the implementer or tester needs may live only in a question, a finding
or feedback: fold its effect into the fields above.
{% if pending | selectattr("output.findings", "defined") | list or pending | selectattr("output.feedback", "defined") | list %}

Each finding and piece of feedback below must be addressed before you choose
`analysed`: change the requirements, or ask the customer when only they can
settle it.
{% endif %}

## The {{ item.type }}: {{ item.title }}

{% include "_requirements.md" %}
{% include "_questions.md" %}
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

The flavour and level of detail to aim for.

~~~yaml
{{ example }}~~~
{% endif %}
