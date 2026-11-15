Challenge this {{ item.type }} before the customer decides whether to play it.
Do not change any files.

Read it against what the customer said, in their answers and feedback below,
and against the repository as it is now: `README.md`, the glossary, the
personas file and the code the {{ item.type }} touches.

Submit your findings, each with a short `concern`. Choose `sound` when none of
them needs the {{ item.type }} to change; any you submit with it are notes for
the customer. Otherwise choose `rework`.

## The {{ item.type }}: {{ item.title }}

{% include "_requirements.md" %}
{% include "_questions.md" %}
{% set feedback = item.step_outputs | selectattr("output.feedback", "defined") | list %}
{% if feedback %}

## The customer's feedback

{% for entry in feedback %}
- {{ entry.output.feedback }}
{% endfor %}
{% endif %}
{% set earlier = item.step_outputs | selectattr("step", "equalto", step.name) | selectattr("output") | list %}
{% if earlier %}

## Your last findings

The product owner has had these. Check each is addressed rather than raising it
again unchanged.

~~~yaml
{{ earlier[-1].output | yaml }}~~~
{% endif %}
{% for entry in pending if entry.output %}

## What analysis changed ({{ entry.outcome }})

~~~yaml
{{ entry.output | yaml }}~~~
{% endfor %}

## Standards the product owner could propose

Those it did propose are in `standards` above.
{% include "_available_standards.md" %}

## Example findings

~~~yaml
{% include "examples/challenge.yaml" %}~~~
