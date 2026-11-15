{% for standard in available_standards if standard.kind == "rule" %}

### {{ standard.name }}

{{ standard.description }}

{{ standard.body }}
{% endfor %}
