{% for standard in standards %}
## Standard: {{ standard.name }} ({{ standard.kind }})

{{ standard.body }}

{% endfor %}
