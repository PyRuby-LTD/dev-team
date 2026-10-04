Implement this change in the repository at {{worktree}}. You are on branch
{{branch}}; commit your work there.

## Acceptance criteria
{{criteria}}

## Investigation
{{investigation}}
{{revision_notes}}

## Output
Write two files in {{item_dir}}:

1. `implementation.md` - what you changed and why, and the actual output of
   any tests or checks you ran.
2. `implement.json` - exactly this shape, nothing else:

```json
{"done": true, "summary": "one sentence", "checks_passed": true, "notes": ""}
```

Set `done` to false if the criteria turned out to be wrong or impossible, and
explain in `notes`.
