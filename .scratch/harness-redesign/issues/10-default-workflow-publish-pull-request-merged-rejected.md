# 10: Default workflow group 5 - publish, pull request, merged and rejected

**What to build:** Accepting with `pr` syncs and checks the branch again (with resolve on conflict), then the publisher raises a pull request and records its number, summary, API changes, surprises and opinions. The pull request step waits until the pull request is merged, rejected or abandoned. A merge brings the base branch up to date and finishes the item at `done`. A rejection records the pull request's feedback as step output addressed to the implementer, instead of editing a Markdown body. Publish and resolve-publish prompts are drafted for the author's review. This completes milestone 3 apart from standards at `ready`.

**Blocked by:** 09

**Status:** ready-for-agent

- [x] A journey test with a stub `gh` publishes, sees the pull request merged, and finds the base updated and the item at `done`
- [x] A rejected pull request puts its feedback in the implementer's pending input
- [x] The pull request step waits without moving the item while the pull request is open
- [x] The original publication and pull request feedback code is deleted once the steps own it

## Comments

`git:PullRequest` asks `gh pr view <number>` for the pull request the publisher recorded, and moves to `merged` only when GitHub reports it merged. Otherwise the item waits at `pull-request`, asked again at most every 60 seconds. `rejected` and `abandon` are the customer's to choose there: a harness step's outcomes that it never produces are now the customer's, so `dev-team backlog record` and the TUI accept them at that step while refusing `merged`. A harness outcome is not recorded if the customer moved the item on while `gh` was being asked.

`harness:Rejected` records the pull request's submitted reviews, inline and conversation comments as structured `comments` (kind, author, state or location, body), which reach the implementer as pending input. `git:Merged` fetches origin and fast-forwards the item branch's recorded base, leaving the checkout on it. The publisher's branch is pushed by the harness before the publisher runs, as `push = true` asks.

`prompts/publish.md` is redrafted for YAML items from the Publisher notes in `Development patterns.md` and needs the author's review; `prompts/resolve-publish.md` prefaces `resolve.md` rather than repeating it. Preview them with `uv run python -m devteam prompt publish --item <id>`. Points to settle while reviewing:

- `roles/publisher.md` still says to report the pull request URL; the workflow now records the number. The brief is the author's to change.
- The body asks for the item ID and title, API changes, then surprises and opinions, and says not to restate the criteria or how it was tested.

`record = true`, which committed a copy of the Markdown item to `docs/work-items/` on the branch before publishing, is dropped with `devteam/publication.py` rather than ported to YAML items. It can come back behind the publisher's step if the copy in the product is wanted.

The original runner's merged and rejected actions, its pull request polling and the record copy are deleted, with `tests/test_merged.py`, `test_pr_feedback.py`, `test_pr_polling.py`, `test_publish.py`, `test_republish.py`, `test_pr_decision.py`, `test_publication.py`, and the dispatch, runner, dependency and checkout tests that drove items through them. `tests/test_checkout_queue.py` keeps its own fixture now that `test_merged.py` is gone.
