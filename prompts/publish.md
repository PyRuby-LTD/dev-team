Publish this work item from the repository at {{checkout}}. Branch {{branch}}
has already been pushed to origin; its base branch is {{base}}. Do not run
`git push` or `git commit` yourself.

1. Look for an existing open pull request for {{branch}} before creating one:
   run `gh pr list --head {{branch}} --state open --json url`. If the lookup
   fails, report the failure; only a successful empty result means none exists.
2. Prepare a body drawn from the item's acceptance criteria and its
   `## Implementation` and `## Review` sections.
   - If an open PR exists, do not run `gh pr create`. The harness has already
     pushed the new commits. Update its body with
     `gh pr edit <existing-url> --body-file <body-file>`, leaving its title and
     URL unchanged.
   - Only when no open PR exists for the branch, run
     `gh pr create --head {{branch}} --base {{base}} --title <item-title> --body-file <body-file>`.
     This includes first publication and publication after an earlier PR was
     closed. Use the item's title and the prepared body.
3. Record the pull request URL under `## Pull request` in the item body.
   Replace that section's content rather than adding a second heading, or
   add the heading if absent. The section must hold exactly one URL; when
   updating an open PR, record the same URL as before.

Do not merge the pull request and do not change any code. Choose `published`
only when the pull request exists.
