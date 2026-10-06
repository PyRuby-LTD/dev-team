---
id: REQUEST-002
type: request
title: When the publisher publishes a work-item creating a PR in github, it currently
  m
workflow: analysis
step: product-owner-questions
---
When the publisher publishes a work-item creating a PR in github, it currently moves to 'done'. I want to be able to review the PR and either merge it or reject it with comments. Once I've merged or rejected, I would then move the work-item to either merged or rejected. For merged, the local main should be brought inline with origin. For rejected, the PR rejection comments should be read and passed back to implement.

## Product owner findings

Audience: the customer, as the person who reviews and merges pull requests that the publisher opens. Today `publish` goes straight to the terminal `done` step, so the item looks finished before the customer has judged the PR, and a rejection has no route back into the workflow.

Desired outcome: after `publish`, the item waits for the customer's PR decision. Merged closes it and brings local main in line with origin. Rejected returns it to `implement` carrying the PR's review comments.

Decision on the open feedback (how sophisticated the rejection step is): pull the comments into the work item. The implementer runs on codex in a sandbox and has no `gh` access, so a note saying "go and read the PR" cannot be acted on. The rejection step therefore reads the PR's review and comment text with `gh` and writes it under a `## Pull request feedback` heading in the item before handing it to `implement`.

Assumptions:
- The customer reviews and merges or rejects on GitHub itself. The tool does not merge or close the PR; the customer only records the outcome by moving the item.
- A rejected PR stays open. After rework the same branch is pushed again and the existing PR is updated, not a second one opened.
- Feedback is every review body, inline review comment and conversation comment on the PR. A later rejection replaces the earlier `## Pull request feedback` section.
- Local main is brought in line by fetching origin and fast-forwarding. If main has diverged or the checkout is dirty, the step fails with a clear message and changes nothing.
- The existing `accept` -> `done` path (no PR) is unchanged.
- Both new outcome steps are run by the harness, not by an agent. This needs a new kind of harness-owned step beside `check`; the shape is left to the engineer.

Blocker found while capturing work: the capture command (`uv run python -m devteam ...`) could not be run from this session. The session's working directory is the backlog worktree, where `devteam` is not importable, and running it against the repository root was not permitted. No work items have been created.

Work items I intend to capture once that is resolved, under EPIC-003:
1. Story: Hold a published item for the customer's PR decision. Acceptance: `publish` no longer moves to `done`; it moves to a human-owned step offering `merged` and `rejected`; the `accept` -> `done` path is unchanged; the workflow validates.
2. Story: Bring local main in line with origin when a PR is merged. Acceptance: moving to `merged` fetches origin and fast-forwards the base branch; the item ends terminal; a diverged or dirty main fails with a message naming the cause and leaves the repository untouched; tested against a local bare remote.
3. Story: Return a rejected PR's comments to implement. Acceptance: moving to `rejected` reads the PR's reviews and comments with `gh`, writes them under `## Pull request feedback` (replacing any earlier section) and moves the item to `implement`; `prompts/implement.md` tells the implementer to address that section; a failed `gh` call leaves the item at `rejected` with the error shown.
4. Story: Re-publish updates the existing PR. Acceptance: when a PR already exists for the branch, the publisher pushes and updates it, recording the same URL, and does not run `gh pr create` again; `gh` calls the publisher needs are allow-listed in `config/roles.toml`.

## Questions

1. The capture command is not runnable from this session (see the blocker above). Can you either make `uv run python -m devteam --product <repo> backlog capture ...` runnable for this role, or capture the four items above yourself? I will then list their IDs and complete the request.

## Feedback

- **analyse -> product-owner:** I am not sure how sophisticated the rejection step should be. It could just add a note that the PR has been rejected so implement step can review the PR comments, or it could pull the PR rejection comments in the rejection step and add them to the work-item before giving it to implement
