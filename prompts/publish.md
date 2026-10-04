Publish this work item from the repository at {{checkout}}. You are on branch
{{branch}}; its base branch is {{base}}.

1. `git push -u origin {{branch}}`
2. Open a pull request from {{branch}} into {{base}} with `gh pr create`. Use
   the item's title, and a body drawn from its acceptance criteria and its
   `## Implementation` and `## Review` sections.
3. Record the pull request URL under a `## Pull request` heading in the item
   body.

Do not merge the pull request and do not change any code. Choose `published`
only when the pull request exists.
