# 17: A Markdown record of each published work item, committed by a `git:Record` step

**Type:** story

**Status:** needs-triage

**As a** customer reading a product's history
**I want** a Markdown record of each work item committed on its branch and published in its pull request
**So that** the reason for a change lives with the code: anyone reading the repository or the pull request can see what was asked for without the backlog branch.

## Context

The original harness's `record = true` committed a copy of the Markdown work item to `docs/work-items/<id>.md` on the item branch before the publisher pushed it, keeping only its preamble, context and acceptance criteria (`devteam/publication.py`). Issue 10 dropped it with the publication module rather than porting it to YAML items.

The YAML item is not the right thing to commit: its step history and machine-oriented fields are for the harness. Instead, a template renders the finished item as Markdown, in the same way that the TUI's detail view is rendered from `views/detail.md`. The record's content is then a template edit, not a code change.

The record is made by a harness step of its own, `git:Record`, which the default workflow places between `verify-publish` and `publish`. The workflow then shows that a record is made, and another workflow can leave it out. A failure to make the record stops the item at `record`, before anything is published.

## Acceptance Criteria

- [ ] **Given** an item that passes `verify-publish`, **When** the harness runs `record`, **Then** the item branch has a commit holding `docs/work-items/<id>.md`, and the item moves to `publish` with `completed`.
- [ ] **Given** an item published after `record`, **When** its branch is pushed, **Then** the pull request includes the record.
- [ ] **Given** the record, **When** it is read, **Then** it holds the item's identity and requirements as the template renders them, and none of its step history.
- [ ] **Given** a requirement that holds a machine path, such as a home directory, **When** the record is committed, **Then** the path is masked in the committed file.
- [ ] **Given** an item republished after a rejection, **When** its requirements are unchanged, **Then** `record` completes without a new commit; **When** they changed, **Then** the existing record is replaced, not duplicated.
- [ ] **Given** the team's author edits the record template, **When** the next item reaches `record`, **Then** its record follows the edited template without a code change.
- [ ] **Given** a template that fails to render, **When** the item reaches `record`, **Then** the item stays at `record` with the error reported, and the publisher is not run.
- [ ] The base branch gains the record only by merging the pull request, never directly.

## Notes

- `Record` is a `GitStep`, so it holds the checkout and shares `Sync`'s preconditions: a recorded base and nothing uncommitted. It produces only `completed`.
- The template is named in `Record`'s code (for example `views/work-item.md`), not in the workflow. A harness step is named explicitly, so the step's definition stays `owner` and `outcomes`. It is rendered with the same environment and context as prompts and the detail view.
- The template's wording is for the author's review, like the prompts.
- The record is committed after `verify-publish`, so the check does not see it. It is documentation only.
- Journey test: extend `tests/redesign/test_publish_journey.py` to assert the `record` entry in the item's history, that the file exists on `origin/devteam/<id>`, and that it is absent from `main` until the merge. Do not assert on its wording.
- Issue 18 moves the push into a `git:Push` step after this one.
