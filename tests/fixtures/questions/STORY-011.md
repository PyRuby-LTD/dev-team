## Questions

1. If your local main already has everything on origin plus commits of your own that you have not pushed, should marking the PR merged succeed (nothing to pull, your commits stay) or fail until you push? Note that a failed merge step keeps the checkout on the item's branch and makes every other code-changing item wait until you fix the cause and retry, so failing here would stop the pipeline until you push. My recommendation is to succeed.

   **Answer:** It should succeed provided it contains what is currently on origin/main even if it has additional commits that have not been pushed.

