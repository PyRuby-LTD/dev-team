Keep the journey tests in the repository at {{ checkout }} in step with this
{{ item.type }}. You are on its branch, {{ branch }}, made from {{ base }}. Leave
your changes in the working tree: the harness commits them to the branch when
you exit, so do not run `git commit` yourself. Change tests, fixtures, canned
data, stubs and the Makefile's test target only, never the code under test.

From the personas the {{ item.type }} affects, decide for each journey it adds
or changes whether to extend an existing journey test, write a new one, or do
nothing because a test would add too little. Doing nothing is often right.
Leave criteria about logic to the implementer's tests, and criteria about
wording or presentation to the customer.
{% if item.persona_changes %}

Apply the persona changes below to the personas file on this branch.
{% endif %}

Run one test with `{{ harness_command }} check <test>` and the whole suite with
`{{ harness_command }} check`. The latest workflow check log is {{ verify_log }}.
If it shows a failure, work out whether the tests or the code are wrong.

Record in your output:

- `journeys`: each journey you considered, with `action` `extend`, `new` or
  `none`, the personas it walks, and for `none` the reason.
- `defects`: when you choose `defect`, each one naming the failing test, what
  it expected, and the log path `check` printed. Leave the failing test in
  place.

## The {{ item.type }}: {{ item.title }}

~~~yaml
{{ requirements | yaml }}~~~
{% for entry in pending if entry.output %}

## From {{ entry.step }} ({{ entry.outcome }})

~~~yaml
{{ entry.output | yaml }}~~~
{% endfor %}
{% include "_standards.md" %}
