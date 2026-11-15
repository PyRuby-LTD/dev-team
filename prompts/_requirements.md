~~~yaml
{{ requirements.model_dump(exclude_none=True, exclude={"questions": True}) | yaml }}~~~
