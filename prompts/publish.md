Publish the change this {{ item.type }} makes as a pull request from its branch,
{{ branch }}, against {{ base }}, in the repository at {{ checkout }}. The
harness has already pushed the branch. Do not change, commit or push anything,
and do not merge the pull request.

First look for an open pull request from the branch with
`gh pr list --head {{ branch }} --state open --json number`. If the lookup
fails, report the failure rather than guessing; only a successful empty result
means there is none.

- With no open pull request, create one titled with the {{ item.type }}'s
  title, passing the body on standard input so that nothing is written into the
  checkout:

  ```
  gh pr create --head {{ branch }} --base {{ base }} --title "<title>" --body-file - <<'EOF'
  <body>
  EOF
  ```

- With one open, the pushed commits are already on it. Replace its body the
  same way with `gh pr edit <number> --body-file -`, keeping its title.

Choose `published` only when the pull request exists with the body you wrote.
If `gh` fails, exit without submitting and say exactly what failed; the item
stays at this step for the customer to look into.

## The {{ item.type }}: {{ item.title }}

{% include "_requirements.md" %}
{% set recorded = item.step_outputs | selectattr("step", "equalto", "implement") | selectattr("output") | list %}
{% if recorded %}

## What the implementer last recorded

~~~yaml
{{ recorded[-1].output | yaml }}~~~
{% endif %}

## Example output

The pull request's body says the same, in the order your brief gives.

~~~yaml
{% include "examples/publish.yaml" %}~~~
