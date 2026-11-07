Implement this {{ item.type }} in the repository at {{ checkout }}. You are on its
branch, {{ branch }}, made from {{ base }}. Leave your changes in the working
tree: the harness commits them to the branch when you exit, so do not run
`git commit` yourself.

Build what the acceptance criteria ask for, and nothing they do not. Run the
tests you wrote or changed and the tests of the code you modified; the full
suite is run for you after the tester's step. The latest workflow check log is
{{ verify_log }}.
{% if item.glossary_changes %}

Apply the glossary changes below to `glossary.md` on this branch, keeping the
document consistent as a whole rather than appending.
{% endif %}
{% if pending | selectattr("output") | list %}

Everything sent back to you below must be addressed before you choose
`implemented`. Comply with review findings and with feedback; where you
disagree, make the change anyway and raise a tech task with your alternative.
For a tester's defect, fix the code rather than the test.
{% endif %}

Record in your output:

- `branch`: the branch you worked on.
- `libraries_added`: every library you added, with its licence.
- `tech_tasks`: refactors you propose and disagreements you record, each
  naming the change and the target pattern.
- `surprises`: assumptions you made where the item was silent, and anything
  the reviewer or customer would not expect.
- `opinions`: anything you introduced that the item did not ask for.
- `blocked_by`: when you choose `blocked`, exactly what is blocked, what you
  tried and what you need from the customer.

Leave out a field you have nothing for.

## The {{ item.type }}: {{ item.title }}

~~~yaml
{{ requirements | yaml }}~~~
{% for entry in pending if entry.output %}

## Sent back by {{ entry.step }} ({{ entry.outcome }})

~~~yaml
{{ entry.output | yaml }}~~~
{% endfor %}
{% include "_standards.md" %}
