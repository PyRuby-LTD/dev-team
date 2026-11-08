Challenge this {{ item.type }} before the customer decides whether to play it.
Read it against the repository as it is now and against what the customer
said: their answers to the questions and any feedback below. Do not change
any files.

Besides the challenges in your brief, ask:

- Is the {{ item.type }} consistent with itself?
- Does it change a public API, and is every change set out in `scope`?
- Would it change a user journey? Name the journey in a finding.
- Are the personas it names in the personas file or in `persona_changes`?
- Does it deliver value on its own?
- Are the proposed standards right? A missing or unnecessary one is a finding.

Give each finding a short `concern` and, in `finding`, what the item says, why
it does not hold and what would fix it, most damaging first. Choose `rework`
when a finding would change what is built or how it is judged, including one
only the customer can settle: say what must be asked, and the product owner
will ask it. Otherwise choose `sound`, with any minor findings for the
customer to see. Do not manufacture findings.

## The {{ item.type }}: {{ item.title }}

~~~yaml
{{ requirements | yaml }}~~~
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

## Standards

The proposed standards are in `standards` above; judge against these.
{% include "_available_standards.md" %}
