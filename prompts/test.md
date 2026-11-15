Keep the journey tests in the repository at {{ checkout }} in step with this
{{ item.type }}. You are on its branch, {{ branch }}, made from {{ base }}. Leave
your changes in the working tree: the harness commits them to the branch when
you exit, so do not run `git commit` yourself.

The latest workflow check log is {{ verify_log }}. If it shows a failure, work
out whether the tests or the code are wrong.

## The {{ item.type }}: {{ item.title }}

{% include "_requirements.md" %}
{% for entry in pending if entry.output %}

## From {{ entry.step }} ({{ entry.outcome }})

~~~yaml
{{ entry.output | yaml }}~~~
{% endfor %}
{% include "_standards.md" %}
