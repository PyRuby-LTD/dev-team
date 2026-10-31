## Submitting your outcome

Finish by submitting one outcome for {{ item.id }}, with your output as YAML on stdin:

```
{{ harness_command }} backlog submit {{ item.id }} <outcome> <<'OUTPUT'
<output>
OUTPUT
```

The command checks the output at once and says what is wrong; fix it and submit again. The last
submission counts, and the harness records it when you exit.

Outcomes:

{% for outcome in step.outcomes.values() %}
- `{{ outcome.name }}`: {{ outcome.means }}
{% endfor %}

{% if step.output == "requirements" %}
The output holds only the requirement fields you change: {{ requirement_fields | join(", ") }}. Each
replaces the item's field, except `questions`: a question already on the item keeps its place, and a
new one is added to the end.
{% elif step.output %}
The output must fit this JSON Schema:

```yaml
{{ step.output | yaml }}```
{% else %}
This step takes no output: submit with nothing on stdin.
{% endif %}
