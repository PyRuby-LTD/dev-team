Review the change on branch {{branch}} in {{checkout}} against the acceptance
criteria in the work item. Read the diff with `git diff {{base}}...{{branch}}`.
Judge the code, not the `## Implementation` notes. Do not change the code.

The harness ran the project's whole suite on this branch before passing the
item to you; its full output is in {{verify_log}}. Read that log. You may run
it again, or one test, with
`{{harness_command}} check [<test>]`. Do not call `make` directly.

Write your findings under a `## Review` heading in the item body, replacing any
earlier one, most-damaging first. Give each finding the input or state that
triggers it, the wrong result it produces and what would fix it. List the
criteria you found satisfied, with the evidence for each.

Choose `approve` only when every criterion is met and proven. Choose `revise`
otherwise, including when the diff is empty: there is nothing to approve.
