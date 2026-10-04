Investigate this request against the repository at {{worktree}}. Do not change
any files in the repository.

## Request
{{request}}

## Intake notes
{{intake}}

## Output
Write two files in {{item_dir}}:

1. `investigation.md` - what you found: the relevant code, whether the problem
   reproduces or the described behaviour exists, and what you propose to change.
2. `investigate.json` - exactly this shape, nothing else:

```json
{"proceed": true, "reason": "one sentence", "criteria": ["...", "..."]}
```

Set `proceed` to false when the repository does not support the request - for
example the behaviour is already correct, or the change would be wrong. That is
a useful outcome, not a failure.
