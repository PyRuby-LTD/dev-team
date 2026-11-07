{% for standard in available_standards %}

### {{ standard.name }} ({{ standard.kind }})

{{ standard.description }}

{{ standard.body }}
{% endfor %}
