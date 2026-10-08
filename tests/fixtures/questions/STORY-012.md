## Questions

1. Neither the analyst, the challenger nor the implementer can run `gh`, so the JSON field names (notably that reviews carry `submitted_at` and no `created_at`) and the `--paginate` output shape rest on recollection. Please run these once against a PR that has at least one review, one inline comment and one conversation comment, and paste the output (trimmed if long) under your answer: `gh api repos/<owner>/<repo>/pulls/<n>/reviews --paginate`, `gh api repos/<owner>/<repo>/pulls/<n>/comments --paginate`, `gh api repos/<owner>/<repo>/issues/<n>/comments --paginate`. It becomes the stub's fixture. If you would rather not, say so and we will accept the first real rejection as the test.

   **Answer:** See gh_api_10_<call>.txt files in the root
2. If a `PENDING` (unsubmitted) review turns up when the PR is read, should the step fail telling you to submit your review first, as currently drafted in criterion 10? Or should it be treated like any other review?

   **Answer:** Act on the PENDING review comments

3. A pending (unsubmitted) review's inline comments may not be returned by `gh api repos/<owner>/<repo>/pulls/<n>/comments`; if so, your answer to Question 2 needs a fourth call per pending review, and none of us can run `gh` to check. Please start a review on any PR with one inline comment, do not submit it, run `gh api repos/<owner>/<repo>/pulls/<n>/reviews --paginate`, `gh api repos/<owner>/<repo>/pulls/<n>/comments --paginate` and, with the review's `id` from the first, `gh api repos/<owner>/<repo>/pulls/<n>/reviews/<id>/comments --paginate`, and put the three outputs in tracked files (see Question 4). If you would rather not, choose instead: (a) read pending comments through the fourth call, building it from the documented API and accepting that the pending fixture is synthetic; or (b) have the section say plainly that an unsubmitted review exists and its comments were not read.

   **Answer:** Withdrawn: per the customer's later feedback, pending reviews are ignored.

4. Where should the real `gh` output live so the checkout is clean when the item is played? Our suggestion: commit the three per-endpoint `gh_api_10_*` files to `main` under `tests/fixtures/` (and delete or commit `gh_api_10.txt` there too), along with the Question 3 outputs if you supply them. The alternative is the backlog directory.

   **Answer:** Withdrawn: the customer deleted the files; fixtures are written under `tests/fixtures/gh/` by the implementer.

Questions 1 and 2 are answered and folded into the analysis and criteria above. Questions 3 and 4 are closed by the customer's feedback (pending reviews are ignored; the root files were deleted, fixtures go in `tests/fixtures/gh/`). Challenge findings: 1 (pending comments) is resolved by ignoring pending reviews, criterion 10; 2 (untracked fixtures) by criterion 15; 3 (several URLs) by criterion 10c; 4 by the assumptions. No questions remain.

