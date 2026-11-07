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

Write the body for a reviewer who knows the codebase but has not seen the
{{ item.type }}. Keep it to a few lines, leading with the point:

1. `{{ item.id }}: {{ item.title }}` and what the change does, in a sentence or
   two.
2. Every change to a public API, command, file format or schema, or "No API
   changes".
3. Only then anything surprising or unexpected, and any opinion an agent acted
   on outside the {{ item.type }}'s scope, from what the implementer recorded
   below.

Do not restate the acceptance criteria, list the files changed or describe how
it was tested. Do not put absolute paths, home directories or command output in
the body.

Record in your output:

- `pull_request`: the pull request's number.
- `summary`: what the change does, as in the body.
- `api_changes`: the API changes, as in the body.
- `surprises` and `opinions`: those the body raises, each as one line.

Choose `published` only when the pull request exists with the body you wrote.
If `gh` fails, exit without submitting and say exactly what failed; the item
stays at this step for the customer to look into.

## The {{ item.type }}: {{ item.title }}

~~~yaml
{{ requirements | yaml }}~~~
{% set recorded = item.step_outputs | selectattr("step", "equalto", "implement") | selectattr("output") | list %}
{% if recorded %}

## What the implementer last recorded

~~~yaml
{{ recorded[-1].output | yaml }}~~~
{% endif %}
