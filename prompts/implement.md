Implement this {{ item.type }} in the repository at {{ checkout }}. You are on its
branch, {{ branch }}, made from {{ base }}. Leave your changes in the working
tree: the harness commits them to the branch when you exit, so do not run
`git commit` yourself.

The full suite is run for you after the tester's step. The latest workflow
check log is {{ verify_log }}.
{% if pending | selectattr("output") | list %}

Everything sent back to you below must be addressed before you choose
`implemented`.
{% endif %}

Create a tech task with

```
{{ harness_command }} backlog create task "<title>" <<'ITEM'
parent: {{ item.id }}
<fields>
ITEM
```

where `<fields>` is YAML shaped like the example task below, without the
title. The command prints the new task's ID; record each one in `tech_tasks`.
{% set earlier = item.step_outputs | selectattr("step", "equalto", step.name) | selectattr("output") | list %}
{% if earlier %}

Your output describes the whole {{ item.type }}, not only this round. Carry
forward everything you recorded last time that still holds, and add to it.
{% endif %}

## The {{ item.type }}: {{ item.title }}

{% include "_requirements.md" %}
{% for entry in pending if entry.output %}

## Sent back by {{ entry.step }} ({{ entry.outcome }})

~~~yaml
{{ entry.output | yaml }}~~~
{% endfor %}
{% if earlier %}

## What you recorded last time ({{ earlier[-1].outcome }})

~~~yaml
{{ earlier[-1].output | yaml }}~~~

{% endif %}
{% include "_standards.md" %}

## Example task

~~~yaml
{% include "examples/task.yaml" %}~~~
