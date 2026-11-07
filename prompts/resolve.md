Resolve the merge of origin/{{ base }} into {{ branch }}, the branch of this
{{ item.type }}, in the repository at {{ checkout }}. The merge is in progress and
stopped at conflicts in:

{% for entry in pending %}
{% for name in entry.output.conflicts or [] %}
- `{{ name }}`
{% endfor %}
{% endfor %}

Resolve every conflict in one round, keeping the intent of both branches: the
change already on {{ base }} and the change this {{ item.type }} makes. Remove
every conflict marker. Run the tests of the code the conflicts touched. Leave
the resolved files in the working tree: the harness completes the merge when
you exit, so do not run `git add`, `git commit` or `git merge` yourself.

If the two changes cannot both stand, or keeping both needs a decision only the
customer can make, choose `blocked` and give `blocked_by`: which conflict, what
you tried and what you need from the customer. The harness then aborts the
merge, discarding your changes, and returns the {{ item.type }} to ready.

## The {{ item.type }}: {{ item.title }}

~~~yaml
{{ requirements | yaml }}~~~
