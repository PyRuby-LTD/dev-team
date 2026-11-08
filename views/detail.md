# {{ item.id }}: {{ item.title }}

{% if step %}
**Step:** {{ step.name }} in the {{ workflow.name }} workflow, waiting on **{{ step.label() }}**
{% else %}
**{{ item.type | capitalize }}**, not in a workflow
{% endif %}
{% if item.parent %}

**Part of:** {{ item.parent }}
{% endif %}
{% if item.depends_on %}

**Depends on:** {{ item.depends_on | join(", ") }}
{% endif %}
{% if pending %}

## Waiting on this step
{% for entry in pending %}

From **{{ entry.step }}** ({{ entry.outcome }}){% if not entry.output %}, with nothing more{% endif %}

{% if entry.output %}
```yaml
{{ entry.output | yaml }}```
{% endif %}
{% endfor %}
{% endif %}
{% if step and step.outcomes %}

## Outcomes
{% for outcome in step.outcomes.values() %}
- **{{ outcome.name }}** leads to {{ outcome.next }}: {{ outcome.means }}
{% endfor %}
{% endif %}
{% if item.questions %}

## Questions
{% for question in item.questions %}

{{ loop.index }}. {{ question.question }}

   {{ question.answer if question.answer else "_Not answered yet._" }}
{% endfor %}
{% endif %}
{% if work_items %}

## Work items
{% for child in work_items %}
- {{ child.id }}: {{ child.title }}{% if child.step %} ({{ child.step }}){% endif %}

{% endfor %}
{% endif %}
{% set fields = requirements.model_dump(exclude_none=True, exclude={"questions": True, "work_items": True}) %}
{% if fields %}

## Requirements

```yaml
{{ fields | yaml }}```
{% endif %}
