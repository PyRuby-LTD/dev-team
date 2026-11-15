Review the change to this {{ item.type }} on its branch, {{ branch }}, in the
repository at {{ checkout }}. Read the diff with
`git diff {{ base }}...{{ branch }}`. Do not change any files.

The harness ran the project's check on this branch before passing the
{{ item.type }} to you; its full output is in {{ verify_log }}. You may run the
whole suite again with `{{ harness_command }} check`, or one test with
`{{ harness_command }} check <test>`.

Choose `approve` only when you have no findings. Otherwise choose `revise`.

## The {{ item.type }}: {{ item.title }}

{% include "_requirements.md" %}
{% set feedback = item.step_outputs | selectattr("output.feedback", "defined") | list %}
{% if feedback %}

## The customer's feedback

{% for entry in feedback %}
- {{ entry.output.feedback }}
{% endfor %}
{% endif %}
{% for name in ("implement", "test") %}
{% set recorded = item.step_outputs | selectattr("step", "equalto", name) | selectattr("output") | list %}
{% if recorded %}

## What {{ name }} last recorded ({{ recorded[-1].outcome }})

~~~yaml
{{ recorded[-1].output | yaml }}~~~
{% endif %}
{% endfor %}
{% set earlier = item.step_outputs | selectattr("step", "equalto", step.name) | selectattr("output") | list %}
{% if earlier %}

## Your last findings

The implementer has had these.

~~~yaml
{{ earlier[-1].output | yaml }}~~~
{% endif %}
{% include "_standards.md" %}

## Example findings

~~~yaml
{% include "examples/review.yaml" %}~~~
