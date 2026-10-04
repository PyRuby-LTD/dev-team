Review the change on branch {{branch}} in {{worktree}} against its acceptance
criteria. Read the diff with `git diff {{base}}...{{branch}}`. Do not read
implementation.md - you are reviewing the code, not its author's account of it.

## Acceptance criteria
{{criteria}}

## Output
Write two files in {{item_dir}}:

1. `review.md` - your findings, each with the input or state that triggers it
   and the wrong result it produces.
2. `review.json` - exactly this shape, nothing else:

```json
{"verdict": "pass", "findings": [{"summary": "...", "severity": "high"}]}
```

`verdict` is one of `pass`, `revise`, `reject`. Use `reject` when the change
should not exist at all, `revise` when it is the right change done wrongly.
