{% if requirements.questions %}

## Questions and the customer's answers

~~~yaml
{{ requirements.model_dump(exclude_none=True, include={"questions": True}).questions | yaml }}~~~
{% endif %}
