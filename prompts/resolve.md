Resolve the merge of origin/{{base}} into {{branch}} in {{checkout}}.
The previously conflicted files are:
{{conflicted_files}}

Resolve all conflict markers in one round, keeping the intended changes from
both branches. Do not run `git commit` yourself: the harness commits the merge
after `resolved`. If you cannot resolve it, reply `blocked`; the harness will
abort the merge and return the item to ready.
