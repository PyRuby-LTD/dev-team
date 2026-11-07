# 10: Default workflow group 5 - publish, pull request, merged and rejected

**What to build:** Accepting with `pr` syncs and checks the branch again (with resolve on conflict), then the publisher raises a pull request and records its number, summary, API changes, surprises and opinions. The pull request step waits until the pull request is merged, rejected or abandoned. A merge brings the base branch up to date and finishes the item at `done`. A rejection records the pull request's feedback as step output addressed to the implementer, instead of editing a Markdown body. Publish and resolve-publish prompts are drafted for the author's review. This completes milestone 3 apart from standards at `ready`.

**Blocked by:** 09

**Status:** ready-for-agent

- [ ] A journey test with a stub `gh` publishes, sees the pull request merged, and finds the base updated and the item at `done`
- [ ] A rejected pull request puts its feedback in the implementer's pending input
- [ ] The pull request step waits without moving the item while the pull request is open
- [ ] The original publication and pull request feedback code is deleted once the steps own it
