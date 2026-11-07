Review the change to this {{ item.type }} on its branch, {{ branch }}, in the
repository at {{ checkout }}, against the acceptance criteria below. Read the
diff with `git diff {{ base }}...{{ branch }}`. Judge the code, not the
implementer's account of it. Do not change any files.

The harness ran the project's check on this branch before passing the item to
you; its full output is in {{ verify_log }}. Read it rather than trusting any
agent's report of a run. You may run the whole suite again with
`{{ harness_command }} check`, or one test with `{{ harness_command }} check <test>`.

For each acceptance criterion, find the code that meets it and the test that
would fail if it were broken, unit or journey. Where the tester recorded a
journey with no test, judge the reason given: accept it, and the criterion
counts as proven, or say why it needs a test. Expect evidence in proportion to
the change: a changed user journey needs a journey test; a behaviour defect
needs a test that reproduces it; a refactor leaves the API and journey tests
unchanged, or justifies changing them.

Beyond the criteria, raise:

- code that is verbose, inconsistent or more complex than it needs to be, and
  poorly named public methods or arguments;
- long or branching methods that are not justified;
- edge cases and error handling not tested at the right level;
- change that traces back to no criterion and no feedback, including tests
  that assert wording or layout;
- a library added under a copyleft licence;
- code that disagrees with `glossary.md`, or a glossary diff that is not the
  change the {{ item.type }}'s `glossary_changes` ask for;
- the smallest input or state that makes the riskiest part of the change go
  wrong.

Record each finding with a short `concern`, its `location` where there is one,
and in `finding` the input or state that triggers it, the wrong result and what
would fix it, most damaging first. Give each finding an `outcome`: `fix` for
the implementer to address now, or `task` with the `task` to capture instead,
for a stylistic change that would need significant rework. Every finding is a
gate: the implementer addresses each `fix`.

Choose `approve` only when every criterion is met and proven, and every finding
is a `task`. Choose `revise` otherwise, including when the diff is empty: there
is nothing to approve. Do not manufacture findings, and do not wave through a
change you could not prove.

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
{% for name in ("implement", "test") %}
{% set recorded = item.step_outputs | selectattr("step", "equalto", name) | selectattr("output") | list %}
{% if recorded %}

## What {{ name }} last recorded ({{ recorded[-1].outcome }})

~~~yaml
{{ recorded[-1].output | yaml }}~~~
{% endif %}
{% endfor %}
{% set earlier = item.step_outputs | selectattr("step", "equalto", step.name) | selectattr("output") | list %}
{% if earlier %}

## Your last findings

The implementer has had these. Check each `fix` is addressed rather than
raising it again unchanged.

~~~yaml
{{ earlier[-1].output | yaml }}~~~
{% endif %}
{% include "_standards.md" %}
