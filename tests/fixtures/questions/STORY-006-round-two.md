## Questions

1. Agents started by the harness in a product other than dev-team cannot run
   `uv run python -m devteam check` or `backlog capture`, because the module is
   not in the product's uv project and the allow-list forbids `--project`. After
   the alias exists, the tester, reviewer and product owner would fail in a
   foreign product. Should fixing that be part of this story (my
   recommendation: yes, by giving prompts, briefs and the allow-list a harness
   command derived from the checkout path), or a separate story, in which case
   this one delivers only the TUI, analysis, challenge and harness-run steps in
   a foreign product and the [human] criterion is narrowed to those?

   **Answer:** Fix as part of this story. Although adding instructions in README.md is good, I'd like perhaps an install.sh in the root that can check pre-requisites and add the alias to .bashrc if it's not present. I quite like the idea of having a dev-team init in a new repo to do any initial setup / check things like it's got a github origin.

2. You asked for an alias `dev-team` and for `dev-team init`. With the alias
   running `devteam tui`, `dev-team init` cannot work. Which do you want?
   (a) One alias `dev-team` running `python -m devteam`, which opens the TUI
   when given no arguments and accepts every subcommand (`dev-team init`,
   `dev-team check`, `dev-team backlog list`); this is my recommendation and
   changes the CLI so a subcommand is optional. (b) Two aliases, `dev-team`
   (TUI only) and `dev-team-init`.

   **Answer:**

3. An empty Git repository has no base branch, so when an item reaches an
   implement step the harness records a base that does not exist and review and
   publish cannot diff or fast-forward against it. Also, the project check
   (`make regression`) is needed from the `test` step, so a new repository needs
   a `Makefile` before then. Should `init` make a new repository workable, that
   is, create an initial commit on the current branch if there are no commits
   and write a placeholder `Makefile` with a passing `regression` target if none
   exists (my recommendation, so the empty-repository walk-through works end to
   end); or should `init` only report, leaving you to commit and add a Makefile
   yourself, in which case the [human] criterion will say the product already
   has one commit and a Makefile?

   **Answer:**

4. If git has no `user.name`/`user.email`, the first backlog commit may fail on
   some machines (git sometimes derives an identity and commits with a warning).
   Have you seen it fail on your computers? If not, I will treat a missing
   identity as a warning with a clear message and add no recovery code.

   **Answer:**

5. When `install.sh` is rerun from a checkout in a new location and
   `~/.bashrc` already has a `dev-team` alias pointing at the old path, should
   it replace that line with the new path (my recommendation) or leave it and
   report it?

   **Answer:**
