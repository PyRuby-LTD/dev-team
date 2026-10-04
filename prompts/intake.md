Read the request below and decide whether it is ready to investigate.

## Request
{{request}}

## Output
Write two files in {{item_dir}}:

1. `intake.md` - your reading of the request: what is being asked for, what
   you are assuming, and anything that is genuinely ambiguous.
2. `intake.json` - exactly this shape, nothing else:

```json
{"ready": true, "title": "short imperative title", "questions": []}
```

Set `ready` to false and list your questions when you cannot proceed without
an answer. Assumptions you are comfortable stating do not count as questions.
