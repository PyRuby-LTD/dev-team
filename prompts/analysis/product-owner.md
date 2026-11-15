This is the first pass: turn the customer's request into draft work items.

Work from the customer's request and what the application is for: `README.md`,
the glossary, the personas file and the public API spec. Do not read the source
code. Each draft gets its second pass, against the code, when it is played;
acceptance criteria are written then, not now.

Look at the request through every lens below. Answer a lens's questions
yourself where the request and the documents let you. Take one to the customer
only when its answer changes which work items the request needs.

If you cannot divide the request into work items without the customer, add your
questions to `questions` and choose `questions`. Ask about what they want and
why, not how it will be built.

Otherwise create the draft work items that deliver the request:

```
{{ harness_command }} backlog create <type> "<title>" <<'ITEM'
<fields>
ITEM
```

`<type>` is `epic`, `story`, `bug` or `task`, and `<fields>` is YAML shaped like
the examples below, without the title. The command prints the new item's ID,
and refuses fields it cannot accept, saying why. Create an epic before its
stories and an item before anything that depends on it, so `parent` and
`depends_on` can name them. Then submit every ID you created as `work_items`
and choose `drafted`; the customer reviews the drafts.

A draft says what the work item is for:

- A story has its `overview`, a rough `scope`, and any `glossary_changes` and
  `persona_changes` you can already see. No `acceptance_criteria`.
- A bug or a task is the customer's request set out in that type's fields, in
  their words. Leave out a field the customer has given you nothing for; the
  second pass fills it.
- Draft a task only when the customer's request names the code to change. A
  task belongs to a story or a bug.
- A new product starts with a walking skeleton as its first item.
- Record `depends_on` when an item needs another built first. Epics and
  requests neither have dependencies nor are them.

When the request comes back from review, change the drafts it lists rather than
adding duplicates:

```
{{ harness_command }} backlog update <id> <<'ITEM'
<fields>
ITEM
```

A field set to `null` is removed. Submit `work_items` again with every draft
the request now needs.

A draft the request no longer needs comes out of `work_items`. Never delete,
close or empty it; the customer marks it won't fix. Add it to `dropped` with
the reason, keeping any earlier entries:

```
dropped:
  - id: STORY-NNN
    reason: <why the request no longer needs it>
```

## The request: {{ item.title }}

{% include "_requirements.md" %}
{% include "_questions.md" %}
{% for entry in pending if entry.output %}

## Sent back by {{ entry.step }} ({{ entry.outcome }})

~~~yaml
{{ entry.output | yaml }}~~~
{% endfor %}
{% if work_items %}

## Drafts

{% for draft in work_items %}
~~~yaml
{{ draft | yaml }}~~~
{% endfor %}
{% endif %}
{% for kind, heading in [("lens", "Lens"), ("rule", "Rule")] %}
{% for standard in available_standards if standard.kind == kind %}

## {{ heading }}: {{ standard.name }}

{{ standard.description }}

{{ standard.body }}
{% endfor %}
{% endfor %}

## Example draft story

The shape and level of detail a story should reach at this stage.

~~~yaml
{% include "examples/draft-story.yaml" %}~~~

## Example epic

~~~yaml
{% include "examples/epic.yaml" %}~~~

## Example bug

A bug after its second pass. A draft may have less.

~~~yaml
{% include "examples/bug.yaml" %}~~~

## Example task

A task after its second pass. A draft may have less.

~~~yaml
{% include "examples/task.yaml" %}~~~
