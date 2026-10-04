Review the change on branch {{branch}} in {{checkout}} against the acceptance
criteria in the work item. Read the diff with `git diff {{base}}...{{branch}}`.
Judge the code, not the `## Implementation` notes. Do not change the code.

Write your findings under a `## Review` heading in the item body, replacing any
earlier one. Give each finding the input or state that triggers it and the
wrong result it produces.

Choose `approve` when the change satisfies the criteria, `revise` when it does
not.
