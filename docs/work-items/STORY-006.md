---
id: STORY-006
type: story
title: "Launch the team from any product directory"
parent: EPIC-002
workflow: default
step: publish
---

# Launch the team from any product directory

As the customer, I want to check out dev-team once, alias its launcher, and run
that command from any product repository, including an empty Git repository,
so the TUI opens for that product with the same team on every computer.

## Notes

Separate the harness root from the product root. Workflows, role briefs,
prompts and `config/roles.toml` resolve from the dev-team checkout; the product
root defaults to the directory the command is run in, replacing
`config/workspace`. Work items stay in the product as Markdown. Nothing may
depend on agents or skills in the user's home directory. Engine CLIs and their
credentials are prerequisites to document, not things to bundle.

## Analysis

Re-checked against the repository as it is now (main at 67c120d). The earlier
analysis described a `config/workspace` mechanism, skills and a `team/README.md`
that no longer exist; this replaces it. I did not run an empty-repository launch
by hand; findings below are from reading the code and tests.

What exists today:

- The harness/product split is done. `devteam/config.py` defines `ROOT` as the
  checkout. Workflows (`workflow.py`), prompts (`runner.py`), role briefs and
  `config/roles.toml` (`config.py`, `check.py`) all resolve from `ROOT`. The
  product root comes from `--product` (default `.`) in `cli.locate`; work items
  are in `<product>/backlog/`, a `devteam-backlog` worktree made by
  `git.ensure_backlog`, which handles a repository with no commits
  (`worktree add --orphan`). `tests/test_checkout.py` exercises a product
  separate from a temporary workflows directory.
- The old workspace mechanism is already gone: no `config/workspace`,
  `tools/workspace`, `config.workspace()`, `.claude/` skills, coherence agent or
  `team/README.md` are tracked. The only remaining mention is README line 176,
  which describes the `{extra_dir}` placeholder as "(the workspace)"; it is the
  backlog directory (see `config/roles.toml`). Nothing under `devteam/` reads
  `~` or `Path.home()`.
- The README already requires uv and uses `uv sync` / `uv run python -m devteam`
  throughout, with no `pip` or bare `python3`, and its Requirements section
  names uv, git, and the `claude`/`codex` CLIs signed in. `gh` is mentioned only
  under "Before the first real run".
- What is missing is the alias: the README says "Run from the root of the
  product repository, or pass `--product DIR`" but gives no setup for a one-off
  checkout run from elsewhere. There is no console script in `pyproject.toml`,
  so `uv run --project <checkout> python -m devteam` is the entry point.
  `--project` keeps the shell's cwd as the product, which `--directory` would
  not.
- Engine launch failure: `engines.run` catches `OSError` (missing CLI) and
  returns 127. `tests/test_runner.py` covers failures leaving the step and not
  being retried; I found no test that names a missing engine command or checks
  that a scan still succeeds afterwards.
- Nothing starts an agent on launch; `s` in the TUI does that.
- `cli.py` has subcommands `backlog`, `run`, `tui`, `check` with
  `required=True`; there is no `init` and no `help` subcommand, and no shell
  script at the repository root.
- The bare `uv run python -m devteam` appears in `prompts/test.md`,
  `prompts/review.md`, `roles/tester.md`, `prompts/analysis/product-owner.md`
  and README line 156, and the claude allow-list in `config/roles.toml` permits
  only `Bash(uv run python -m devteam *)`. Agents run with the product (or its
  checkout) as cwd, so in a product that is not dev-team that command resolves
  the product's own uv project, where `devteam` is absent.

What would change:

1. README: the alias (via `install.sh` and by hand), `init`, Requirements
   additions, and the "(the workspace)" wording at line 176; and
   `docs/backlog.md` lines 102-107, which show the bare command.
2. A harness command derived from `ROOT` for prompts, briefs and the allow-list.
3. A new `init` subcommand and a `help` subcommand.
4. A root `install.sh`.
5. Tests for the criteria below.
6. No deletion work: the retirement of `config/workspace` is already complete.

Note on the isolation criterion: `ensure_backlog` adds `/backlog/` to the
product's `.git/info/exclude` and creates a worktree and branch in that
product. That modifies the product being used, but not the other product or the
checkout, which is what the criterion tests.

## Challenge

Verdict: sound. This is the sixth challenge, of the item as amended after the
fifth. All four of the fifth challenge's findings are in the text and in the
criteria (the GitHub origin rule, the quick-start state defined on the current
branch, unconditional `-P`, the `init` warnings criterion). A competent
engineer could build this as written and a reviewer could tell whether they
had. Nothing below changes what gets built or needs the customer; they are
points for the implementer and tester to settle the obvious way.

What I checked against the repository at 67c120d, by reading: `cli.py`
(subcommands, `required=True`, `locate`), `config.py` (`ROOT`, `Role.brief`),
`git.py` (`ensure_backlog`, `current_branch`), `runner.py` (`PR_URL`,
`take_checkout`, `render`, the cwd passed to the engine, the failure report
with the log path), `engines.py` (`build_argv`, `OSError` to 127), `check.py`
(no `env` passed), `config/roles.toml`, `pyproject.toml`, README lines 32-50,
156 and 176, and `docs/backlog.md` lines 102-107. Every claim the item makes
about them holds. `git grep "uv run python -m devteam"` finds the bare command
exactly where the item says and nowhere else outside `docs/work-items`.
`.venv/lib/python3.13/site-packages/dev_team.pth` exists, which is what the
`-P` assumption relies on. The customer's remote is the scp-like form the
origin rule names.

Not checked by running: commands outside the checkout, and `uv run python -P`
inside it, were refused in this session too (the session's own allow-list is
the bare `uv run python -m devteam *`). So the alias, `-P` and the allow-list
pattern have still never been executed by anyone on the team. The subprocess
and shadowing criteria settle the first two as soon as they are written; the
implementer should write those two tests first, before `init` and
`install.sh`, because everything else assumes them.

Residual points, none blocking:

1. **The one assumption no test can settle is that `claude` honours an
   allow-list pattern carrying a path** (`Bash(uv run --project <ROOT> python
   -P -m devteam *)`). The item says so and leaves it to the [human] criterion,
   which is the last thing to happen. The cheapest check is one command by the
   customer before playing, or by the tester first: from any directory outside
   the checkout, `claude -p "run: uv run --project <checkout> python -P -m
   devteam help" --allowedTools "Bash(uv run --project <checkout> python -P -m
   devteam *)"` and see that it is not refused. The existing pattern has the
   same shape and works today, so I rate the risk low.
2. **`help` is described two ways.** The assumption says it "prints the same
   text as `--help`"; the later decision says top-level help followed by the
   `backlog` help. The subprocess criterion requires the `backlog` actions in
   the output, which only the second gives, so the second governs. The first
   sentence should go when the item is next touched.
3. **"Nor a warning" in the second-run criterion means the `origin` warning.**
   `init` also warns when `claude`, `codex` or `gh` is missing from `PATH`, so
   that test must put the stubs in `tests/stubs` on `PATH` or it fails on a
   machine without `codex`.
4. **Existing codebase with a Makefile that already has a `regression`
   target:** the item does not say whether the wire-up message is printed. It
   should not be (there is nothing to wire up, and this repository is such a
   product); only "the backlog is set up" needs reporting. No criterion
   covers the output in that case; the "unpushed work" criterion could assert
   it.
5. **Quick-start state with `origin` holding the branch at a different
   commit:** by the step order and the exit guarantee, `init` still makes the
   local Makefile commit and then declines to push, leaving a local root
   commit unrelated to `origin`. That follows from answer 6 (no edge-case
   handling) and the warning tells the customer; the criterion could say "one
   local commit" so the test pins it.

Traced to the customer and found in order: the alias and README (first
feedback entry), agents reaching the harness, `install.sh` and `init`
(answer 1), one alias plus `help` (answer 2), the failing placeholder
Makefile, the GitHub origin requirement and the commit (answer 3), no
identity recovery (answer 4), the non-replacing alias (answer 5), and the
quick-start limit (answer 6). The departures are labelled as the analyst's
own: `--project` and `-P` added to the customer's alias wording, "main" read
as the current branch, exit 0 on an existing alias, refusal of GitHub
Enterprise and SSH host aliases, and the path-character restriction. Four
deliverables in one story is the customer's choice in answer 1.

## Response to fifth challenge

All four findings accepted; none needs the customer. Nothing was run; the
earlier "commands outside the checkout" limit still applies, so these rest on
reading `runner.py` (`PR_URL`) and the customer's remote
(`git@github.com:PyRuby-LTD/dev-team.git`).

1. The GitHub origin rule is now stated once under Assumptions (read
   `remote.origin.url`; host exactly `github.com`; three URL forms, with or
   without `.git`; other hosts refused). Criteria added for the scp-like form,
   the other two forms through `insteadOf`, and the look-alike host.
2. The quick-start state is now defined on the current branch (`HEAD` unborn,
   or one root commit changing only `Makefile`); the `devteam-backlog` commit
   from an earlier launch does not count. Same commit on `origin` means
   "already set up", no warning; a differing commit warns. Criteria added for
   `init` after `backlog list`, and the second-run criterion asserts no wire-up
   message and no warning.
3. `-P` is unconditional. The conditional was removed from the assumption, and
   the shadowing criterion is two-sided (without `-P` it prints "shadowed").
4. A criterion now covers the `claude`/`codex`/`gh` warnings.

(This supersedes the "`-P` is dropped if the test shows it unnecessary" wording
in the responses below.)

## Response to fourth challenge

1. Accepted and put to the customer as Question 6. The answer: build for the
   empty repository only; in an existing codebase create a Makefile if none and
   tell the customer to wire up `make regression` and commit. So `init` now
   commits and pushes only in the quick-start state, and never pushes earlier
   local commits or other branches. The fetch, ahead/behind and stale-clone
   handling I had proposed is dropped as out of scope; the criteria for those
   cases are replaced by the two "existing codebase" criteria.
2. Accepted. The superseded sentences (old order, uncommitted-Makefile rule,
   shorter character list, "install.sh refuses such a path", "allowed to blow
   up") were rewritten in place; the push guarantee and path rule each appear
   once under "Decisions after the third and fourth challenges".
3. Accepted as a precaution. By reading, `python -m` puts the current directory
   on `sys.path`, so shadowing is plausible; I could not run the check in this
   session (commands outside the checkout were refused). The harness command
   and alias gain `-P`, a test with a `yaml.py` is added, and `-P` is dropped
   if the test shows it unnecessary. This is a small departure from the
   customer's alias wording and is stated as such.
4. Accepted. `docs/backlog.md` lines 102-107 are in scope: a documentation
   criterion, the `git grep`, and the change list now cover it.

## Response to challenge

1. Agents reaching the harness: confirmed by reading. Agents run with the
   product (or its checkout) as cwd (`runner.py` passes `self.checkout or root`),
   and prompts and briefs tell them to run `uv run python -m devteam ...`
   (`prompts/test.md`, `prompts/review.md`, `roles/tester.md`,
   `prompts/analysis/product-owner.md`). In a product that is not dev-team that
   resolves the product's own uv project, where `devteam` is absent, and the
   claude allow-list in `config/roles.toml` permits only
   `Bash(uv run python -m devteam *)`. (Superseded in detail by the fourth
   challenge: the command now also carries `-P`.) I could not run it from outside the
   checkout in this session either, so it rests on the code. This is a scope
   decision, so it is asked below. Recommended mechanism if in scope: a
   harness-command value derived from `ROOT`
   (`uv run --project <ROOT> python -m devteam`) substituted into prompts and
   role briefs and into the allow-list in `roles.toml`.
2. The alias has not been run by hand. A subprocess criterion is added so the
   documented command line is exercised, not only `locate`.
3. The empty-repository criterion now opens the TUI in the test.
4. Git identity: `git.ensure_backlog` commits "Start the backlog" and so needs
   `user.name` and `user.email`. A failure there leaves a half-made `backlog/`
   worktree that is accepted on the next launch (`backlog/.git` exists). The
   Requirements criterion now names the git identity and the product's
   `Makefile` with `make regression`. Recovering from a failed first commit is
   a small hardening included here, with a test.
5. Criteria already true at 67c120d are labelled "guard"; the README pattern is
   now `\bpip\b`.

## Response to second challenge

Checked against the code: `cli.py:87` has `required=True` subparsers and `tui`
takes no arguments, so `dev-team init` with the current alias becomes
`devteam tui init` and is rejected (finding 1 holds). `runner.py:199-208`
records `branch.<branch>.base` from the current branch, and `git.fast_forward`
and the review/publish prompts use it; in a repository with no commits that
base does not exist (finding 2 holds; I have not run the `git switch -c`
check, so it rests on reading). Finding 3 holds: the allow-list is formatted
in `engines.build_argv`, prompts in `runner.render`, briefs are read in
`config.Role.brief`; README line 156 also names the bare command. Finding 4:
`ensure_backlog` leaves `.gitignore` staged on the unborn branch and the first
`Repository.commit` uses `add -A`, so by reading the half-made state repairs
itself; I have no evidence of the failure on the customer's machines. Finding 5
holds.

The questions were then put to the customer and answered (below). Outcome:
finding 1 resolved by the customer (one alias that is the whole command prefix,
no `dev-team-init`); finding 2 resolved by `init` creating and committing a
Makefile, which also gives the empty repository a base branch; finding 3
accepted as restated in the criteria; finding 4 resolved by the customer (no
recovery code; a missing identity blows up when `init` commits); finding 5
accepted, and the stale-alias question answered by the customer (warn, do not
replace). The "Decisions" and "Acceptance criteria" sections were rewritten to
match; the earlier drafts are gone.

## Response to third challenge

All five findings accepted; none needs the customer. I could not run the
environment check in finding 5(c) in this session either (command refused), so
it is stated as a README requirement and a human-verifiable point, not a
finding of fact: `check.run` passes no `env` (read in `check.py`), so the
`uv run` environment is inherited.

1. `init` is defined by its end state: on exit 0 the current branch has at
   least one commit and `refs/remotes/origin/<branch>` equals `HEAD`. Rules
   below under "Decisions after the third challenge". A rerun after a failed
   commit or push completes the work. Test added.
2. `init` refuses on a `devteam/*` branch or a detached HEAD, before changing
   anything, and the report names the branch it committed to and pushed. Not
   restricted to the literal branch `main`; the customer's "to main" is read as
   "the branch you are on" (stated assumption, unchanged).
3. `help` criterion strengthened to cover every subcommand and the `backlog`
   actions; subparsers `validate` and `capture` get help strings.
4. The path check moves into the code that derives the harness command from
   `ROOT`; `install.sh` keeps an early refusal. `(` and `)` added.
5. (a) corrected to "harness command"; (b) the README usage section shows the
   `dev-team` alias form; (c) README Requirements gains the Makefile-selects-its-
   own-environment point.

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

   **Answer:** Alias 'dev-team' should just alias 'uv run python -m devteam'. It's okay for that to fail if there is no command given provided there is a 'help' command that documents the options.

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

   **Answer:** initially 'init' should check there is a makefile and if not it should create one. The regression target should error when invoked with an unimplemented warning. If there is no github origin then the project should fail. The init could commit the initial makefile to main. NOTE: I want 'init' to grow a bit over time, allowing the target repo to define overrides to agent prompts and custom workflows, but that's for a later story.

4. If git has no `user.name`/`user.email`, the first backlog commit may fail on
   some machines (git sometimes derives an identity and commits with a warning).
   Have you seen it fail on your computers? If not, I will treat a missing
   identity as a warning with a clear message and add no recovery code.

   **Answer:** Let it blow up during init when it tries to push the makefile.

5. When `install.sh` is rerun from a checkout in a new location and
   `~/.bashrc` already has a `dev-team` alias pointing at the old path, should
   it replace that line with the new path (my recommendation) or leave it and
   report it?

   **Answer:** if dev-team alias exists, exit with a warning message that it already exists.

6. In a product that already has commits, may `dev-team init` push the branch
   you are on to GitHub, including commits you have not pushed yet, or should it
   push only the Makefile commit it made itself and otherwise just tell you the
   branch is not on origin (or is ahead of or behind it)? My recommendation is
   the narrow answer: push only commits `init` made, otherwise change nothing,
   say how the branch differs from `origin`, and carry on to set up the backlog
   with a warning. Pushing earlier local commits or creating a new branch on
   GitHub cannot be undone once others have fetched.

   **Answer:** init is intended to quick-start using dev-team. You are seeking lots of edge-cases here when the intent is to make the happy path easy. Build for the case where the repo is empty. In other cases with an existing codebase, create a makefile if none exists and output a message to get the user to wire up the make regression target and commit before running 'dev-team tui'

## Decisions from the customer's answers

Agent access to the harness is in this story, as are `install.sh` and
`dev-team init`.

Decided by the customer:

- The alias is `dev-team`, and it is `uv run --project <checkout> python -m
  devteam` (this analysis adds `-P`; see the harness-command assumption). Bare `dev-team` may fail, provided a `help` command documents the
  options. The TUI is `dev-team tui`. `--project` (not `--directory`) keeps the
  shell's cwd as the product.
- `install.sh` in the checkout root checks prerequisites and adds the alias to
  `~/.bashrc` if absent. If a `dev-team` alias already exists it exits with a
  warning that it already exists, and does not replace it.
- `dev-team init` is a new subcommand acting on the product root. It checks for
  a `Makefile` and creates one if absent, whose `regression` target errors with
  an "unimplemented" warning. If there is no GitHub `origin`, `init` fails. In
  an empty repository (answer 6: build for the happy path) it commits the new
  Makefile to the current branch and pushes it. In a repository that already
  has commits it writes the Makefile if none exists, commits and pushes
  nothing, and tells the customer to wire up `make regression` and commit
  before running `dev-team tui`. A missing git identity or a failed push stops
  `init` with git's message and no recovery code; because the steps test
  state, a rerun completes the work.
- Later stories will let `init` grow (per-product prompt overrides, custom
  workflows). Not in this story.

Assumptions I am comfortable with:

- Harness command: one value derived from `ROOT`, `uv run --project <ROOT>
  python -P -m devteam`, substituted into prompts (`runner.render`), role briefs
  (`config.Role.brief`) and the claude allow-list (`engines.build_argv`, from
  `config/roles.toml`). Checked-in files carry a placeholder. The codex
  implementer prompt does not call the harness, so only the claude allow-list
  needs it. The path restriction is under "Decisions after the third
  challenge". `-P` (Python 3.11+; the project requires 3.13) stops `-m` putting
  the current directory, which is the product, first on `sys.path`, so a
  product's own `yaml.py` or `rich/` cannot shadow what `devteam` imports. This
  is the one departure from the customer's "alias `uv run python -m devteam`":
  the alias is the same command with `-P` added. `-P` stays; it is not
  conditional. `devteam` itself still imports because the checkout is
  installed into its environment (`dev_team.pth`; `pyproject.toml` has a build
  system). Not run in this session.
- A bare `dev-team` keeps argparse's behaviour: usage on stderr, nonzero exit.
  A `help` subcommand prints the same text as `--help`. `required=True` on the
  subparsers stays.
- "Commits to main" means the current branch of the product. In a repository
  with no commits that is the unborn branch, so the Makefile commit is the
  initial commit. That also gives `Runner.take_checkout` a base that exists (it
  records `branch.<branch>.base` from the current branch; on an unborn branch
  review's `git diff {{base}}...{{branch}}` and `git.fast_forward` would have
  nothing to resolve). Launching the TUI without `init` is still allowed and
  works; an item reaching an implement step in a repository that has never had
  a commit is not guarded, and the README says to run `init` first.
- `init` never runs `git init`, never edits an existing Makefile, and warns if
  a Makefile has no `regression` target. The step order is under "Decisions
  after the third challenge".
- `init` also reports, as warnings only, `claude`, `codex` or `gh` not on PATH
  (tested; see the `init` warnings criterion).
- GitHub origin rule (stated once): the configured value of
  `git config --get remote.origin.url` (not `git remote get-url`, which expands
  `url.<base>.insteadOf`) has host exactly `github.com`, in one of the forms
  `https://github.com/<o>/<r>`, `git@github.com:<o>/<r>` and
  `ssh://git@github.com/<o>/<r>`, with or without a trailing `.git`. Other
  hosts (GitHub Enterprise, SSH host aliases) are refused, consistent with
  `PR_URL` in `runner.py`. The customer's own remote is the scp-like form. The
  push itself goes through the git-resolved URL, so a test can redirect it to a
  local bare repository with `insteadOf`.
- The placeholder Makefile's `regression` target prints a message containing
  "unimplemented" to stderr and exits nonzero, so `dev-team check` fails in a
  new product until the customer defines the target. That is intended.
- `install.sh` checks, reporting every missing one in a single run: uv and git
  (required, nonzero exit), git `user.name` and `user.email`, `claude`, `codex`,
  `gh` (warnings, exit 0). It installs nothing and does not test sign-in. The
  prerequisite checks run before the alias step. An existing alias is a warning
  and exit 0 (assumption: the customer said "exit with a warning", and a rerun
  is not an error); it is not replaced even if it points at an old path.
- `~/.bashrc` is the only shell file handled; bash is the customer's shell.

Decisions after the third and fourth challenges (the `init` order and the path
restriction; each rule is stated once, here):

- `init` order becomes: (1) inside a Git repository; (2) current branch is
  readable (`git symbolic-ref --short HEAD`, which works on an unborn branch),
  is not detached and does not start with `devteam/`; (3) `origin` is a GitHub
  URL (the GitHub origin rule under Assumptions); all three checked before anything is created. Then (4) if
  `Makefile` is absent, write it; (5) if the repository is in the quick-start
  state (below), commit the Makefile (only that file; an existing untracked
  Makefile is committed unchanged) and push; otherwise commit and push nothing
  and print the wire-up message; (6) `git.ensure_backlog`; (7) report what was
  done, naming the branch where a commit or push happened. Any git failure in
  (4) to (6) exits nonzero with git's message, no recovery code. A rerun after
  such a failure picks up where it stopped because the steps test state, not
  "did I just write the file". A tracked or existing Makefile is never
  rewritten.
- Quick-start state (customer answer 6), defined on the current branch, not on
  the repository: `HEAD` is unborn, or `git rev-list HEAD` yields exactly one
  commit, a root commit that changes only `Makefile` (so a rerun after a failed
  push still counts). Commits on other branches, including `devteam-backlog`
  (which `git.ensure_backlog` creates on any `backlog`, `run`, `tui` or `check`
  launch), do not count. Only in this state does `init` commit or push. It
  pushes when `git ls-remote --exit-code origin refs/heads/<branch>` finds no
  such branch. If `origin` has the branch at the same commit as `HEAD`, `init`
  pushes nothing, reports that the product is already set up, and does not
  warn. If `origin` has the branch at a different commit it pushes nothing and
  warns. No fetch, divergence or ahead/behind handling: those edge cases are
  out of scope. On a rerun in the quick-start state with the Makefile already
  committed, the wire-up message is not printed (it belongs to the existing
  codebase state only).
- Existing codebase (any other state): `init` writes a placeholder `Makefile` if
  none exists, leaves it uncommitted, pushes nothing, and prints a message to
  wire up the `regression` target and commit before running `dev-team tui`. If a
  Makefile exists without a `regression` target it warns instead. The backlog is
  still set up and exit is 0.
- Guarantee on exit 0: in the quick-start state the current branch has the
  Makefile commit and `origin` has that branch at the same commit (or a warning
  says `origin` already had the branch); otherwise no commit was made and
  nothing was pushed.
- The harness command is derived in one function in `devteam/config.py` which
  raises a clear error if `ROOT` contains whitespace or any of `* ? [ ] ( ) " '
  \` (no quoting is attempted in the allow-list pattern; the alias quotes the
  path). `run` and `tui` and `init` fail at launch with that error (they are the
  commands that start agents or report on them); `help`, `backlog` and `check`
  do not need the value and are unaffected. `install.sh` also refuses early.
- `help` output shows `--product`, a one-line description of every subcommand
  including `init` and `help`, and the `backlog` actions (`validate`, `list`,
  `capture`, `move`), implemented by giving every subparser a help string and
  having `help` print the top-level help followed by the `backlog` help. The
  README points to `dev-team backlog --help` for the arguments.

## Acceptance criteria

Guards (already true at 67c120d, not delivered scope) are marked as such.

Documentation (checked by reading the README):

- README documents, for a uv user, the `install.sh` route and the manual route:
  `alias dev-team='uv run --project "<checkout>" python -P -m devteam'` in
  `~/.bashrc`, with the checkout as a placeholder. It states that the command
  acts on the directory it is run from, that `dev-team tui` opens the TUI, that
  `dev-team help` lists the commands, and that `dev-team init` should be run
  first in a new product. It documents what `init` does and that it fails
  without a GitHub origin.
- README Requirements names uv, git with `user.name` and `user.email`, a GitHub
  `origin` for the product, the engine CLIs signed in, `gh` for publishing, and
  that the product needs a `Makefile` with `make regression` from the `test`
  step onwards (`init` writes a placeholder that fails until replaced). It
  also says the Makefile's targets must select the product's own environment
  (for a uv product, `uv run ...`), because `dev-team` runs `make` with the
  checkout's virtual environment inherited.
- README usage section (currently lines 44-50) shows the `dev-team ...` form,
  and says it is the alias for `uv run --project <checkout> python -P -m
  devteam`; no README line shows the bare `uv run python -m devteam` as a
  command to run (`git grep -n "uv run python -m devteam" -- README.md`
  returns nothing).
- `docs/backlog.md` lines 102-107 show `dev-team ...` instead of
  `uv run python -m devteam ...`, with a sentence saying `dev-team` is the
  alias set up in the README (`git grep -n "uv run python -m devteam" --
  docs/backlog.md` returns nothing).
- README line 156 uses the harness-command placeholder or wording rather than
  the bare `uv run python -m devteam check`; "(the workspace)" no longer
  describes `{extra_dir}`.

Tests (each can fail on a wrong implementation):

- Shadowing: in a temporary `git init` directory containing a `yaml.py` whose
  only line is `raise SystemExit("shadowed")`, `uv run --project <checkout>
  python -P -m devteam backlog list` exits 0 and does not print "shadowed";
  the same command without `-P` prints "shadowed" (so the test proves the flag
  matters). `-P` is kept either way.
- Subprocess: from a temporary `git init` directory outside the checkout,
  `uv run --project <checkout> python -P -m devteam backlog list` exits 0 and acts
  on that directory's backlog, not the checkout's. Likewise `... help` exits 0
  and its output shows `--product`, every subcommand (`init`, `help`, `tui`,
  `check`, `backlog`, `run`) each with a non-empty description, and the
  `backlog` actions `validate`, `list`, `capture` and `move`; with no arguments
  it exits nonzero.
- With cwd in a product and the checkout elsewhere, `locate` returns that
  product's `backlog`, and the workflows, prompts, role briefs and `roles.toml`
  paths are under `ROOT`, not the product.
- In a `git init` repository with no commits, `locate` succeeds, the TUI (driven
  as in `tests/test_tui.py`) shows an empty list, and the runner has started no
  step and made no engine call.
- Given two product repositories and one checkout, capturing and moving items in
  one leaves the other product's files and `git status --porcelain`, and the
  checkout's `git status --porcelain`, unchanged. Excluded: the `/backlog/`
  entry in `.git/info/exclude`, and the worktree and branch, in the product
  being used.
- With the engine command missing, and separately with an engine that exits
  nonzero, running an agent-owned step leaves the item at its step, reports the
  failure with the transcript path, and a backlog scan still succeeds.
- Agents: for a product outside the checkout, the argv from
  `engines.build_argv` contains exactly `Bash(uv run --project <ROOT> python -P
  -m devteam *)` and no `Bash(uv run python -m devteam *)`; with `ROOT` patched to
  a path containing a space, `*` or `(`, deriving the harness command raises, and
  `run`, `tui` and `init` exit nonzero with that message while `help` still
  exits 0; the rendered prompts for
  test, review and product-owner analysis and the tester brief contain the same
  command and not the bare one; running that command with `help` from a
  temporary product directory exits 0. `git grep -n "uv run python -m devteam"
  -- prompts roles config docs` returns nothing. Whether `claude` honours the pattern
  is shown only by the [human] criterion.
- `init` in a `git init` repository with no commits, a GitHub-looking `origin`
  rewritten to a local bare repository with `url.<bare>.insteadOf`, and no
  Makefile: exits 0; creates a Makefile whose `make regression` exits nonzero
  with "unimplemented" in its output; the Makefile is the only commit on the
  current branch; the bare repository has that branch at the same commit; the
  backlog worktree exists; `Runner.take_checkout` for a new item then records a
  base that `git rev-parse --verify` resolves.
- `init`, second run: `git status --porcelain`, the current branch's `git log`,
  the bare repository's refs and the backlog branch's `git log` are identical to
  after the first run; the output says the product is already set up and
  contains neither the wire-up message nor a warning.
- `init` after an earlier launch: in a `git init` repository with no commits on
  the current branch, run `dev-team backlog list` first (which makes the
  `devteam-backlog` commit), then `init`; it reaches the same end state as the
  first-run criterion (Makefile is the only commit on the current branch, bare
  repository at that commit, base resolvable).
- GitHub origin forms: `init` accepts `origin` configured as
  `git@github.com:o/r.git`, `https://github.com/o/r`, and
  `ssh://git@github.com/o/r.git` (each redirected to a local bare repository
  with `insteadOf`, so the check must read `remote.origin.url` and not the
  expanded value); it exits nonzero, changing nothing, for
  `https://github.com.example.com/o/r.git`.
- `init` warnings: with `gh` (and separately `claude`, `codex`) absent from
  `PATH`, `init` still exits 0 and names the missing command in its output.
- `init` failures, each exiting nonzero and leaving the directory as it was
  (`git status --porcelain` empty, no new commits, no `backlog/`, no Makefile):
  not a Git repository (and no files created); no `origin`; an `origin` that is
  not GitHub (for example `https://example.com/o/r.git`); the current branch is
  `devteam/STORY-001` (with at least one commit); HEAD is detached. The success
  report names the branch committed to and pushed.
- `init` with an existing tracked Makefile: it is not modified and no commit is
  made; one without a `regression` target produces a warning. In a repository
  with no commits, an existing untracked Makefile is committed unchanged, and
  only that file; in a repository with commits it is left untracked and
  unchanged.
- Rerun after failure, commit: with no git identity (`GIT_CONFIG_GLOBAL=/dev/null`,
  `user.useConfigOnly=true`) and no Makefile, `init` exits nonzero with git's
  message and no recovery is attempted; after the identity is set (and the
  untracked Makefile left in place), running `init` again exits 0 with the same
  end state as the first-run criterion (one commit, bare repository at that
  commit, backlog worktree present).
- Rerun after failure, push: with `origin` pointing at a missing path the first
  `init` exits nonzero after committing; once the bare repository exists, a
  second `init` exits 0 and the bare repository has the branch at `HEAD`.
- Existing codebase, no Makefile: in a repository with two commits and no
  Makefile, `init` exits 0, writes the placeholder `Makefile` uncommitted
  (`git status --porcelain` shows it untracked, apart from the excluded
  backlog), makes no commit, leaves the bare repository's refs unchanged, creates
  the backlog worktree, and its output tells the customer to wire up
  `make regression` and commit before `dev-team tui`.
- Existing codebase, unpushed work: a branch `spike` with commits `origin` lacks
  and a tracked Makefile, and separately `main` three commits ahead of the bare
  repository: `init` exits 0, the bare repository's refs are unchanged and no
  commit is made.
- Quick-start state with `origin` already holding the branch at a different
  commit: `init` pushes nothing, warns, and exits 0. (At the same commit it is
  the second-run case above: no warning.)
- `install.sh`, run with `HOME` set to a temporary directory and `PATH` set to
  a temporary directory of stubs for uv, git, `claude`, `codex`, `gh` plus
  symlinks to the real `bash`, `grep` and the other utilities the script uses:
  (a) the alias is appended to that `.bashrc` once; a rerun leaves the file
  byte-identical and prints a warning that the alias exists; (b) with several
  prerequisites missing, one run reports all of them and exits nonzero when uv or
  git is among them; (c) it exits 0 with warnings when only an engine CLI, `gh`
  or the git identity is missing; (d) the checkout's `git status --porcelain` is
  unchanged and the only file written under the temporary home is `.bashrc`;
  (e) given a checkout path containing a space, or `*`, it exits nonzero with a
  message and writes no alias. `bash -n install.sh` passes.
- Guard (already true; `install.sh` legitimately touches `~/.bashrc` and is
  outside `devteam/`): `git grep -nE "config/workspace|tools/workspace" -- .
  ':!backlog' ':!docs'`, `grep -rnE "Path\.home|expanduser|environ\[.HOME"
  devteam` and `grep -nE "\bpip\b|python3" README.md` return nothing.
- The existing suite passes (`uv run python -m unittest discover -s tests`).

Human:

- [human] Given a fresh checkout on another computer and the documented
  prerequisites, when the customer runs `install.sh`, opens a new shell, makes a
  Git repository with a GitHub origin, runs `dev-team init` and then `dev-team
  tui`, then the TUI opens with an empty backlog; after the customer replaces the
  placeholder `regression` target, an item taken through test and review has its
  agents run the harness command (`check`, `backlog capture`) and capture items, with the claude agents not
  refused by the allow-list, without home-directory resources or source edits.

Size note for the challenger: this is now four deliverables (harness command for
agents, `init`, `install.sh`, README). The challenger or customer may prefer to
split it; I think it is implementable as one story because the [human] criterion
needs all four.

## Original acceptance criteria

- Given a dev-team checkout elsewhere and the documented alias, when it is run
  from a product directory, then the TUI opens on that directory's work items
  using the checkout's workflows, roles and prompts.
- Given an empty Git repository with no commits, when launched, then the TUI
  opens with an empty backlog and no agent is started.
- Given two product directories using one checkout, when items are changed in
  one, then the other product and the checkout are unmodified.
- Given a missing engine CLI or credentials, when an agent-owned step is run,
  then viewing still works and the failure is reported without moving the item.
- [human] Given a fresh checkout on another computer and the documented
  prerequisites, when the customer follows the setup, then it works without
  home-directory resources or source edits.

## Feedback

- **analyse -> analysis:** I use 'uv' for managing python. Include in the README.md instructions for creating an alias 'dev-team' in .bashrc that runs the dev-team tui in $PWD
- **rework -> analysis:** Passing this back to analysis as I think this was created before the challenger step was created. I want the challenger step to review this story


## Implementation

Implemented the launcher, agent command, product quick-start and documentation.
Changes are left in the working tree; no commit was made.

- Added a single validated harness command derived from `config.ROOT`, with
  `--project` and unconditional `-P`. Prompts, the tester brief and the Claude
  allow-list substitute it. `run`, `tui` and `init` validate the path before
  doing work; other commands do not require it.
- Added `help` with top-level commands and backlog actions, preserving the
  required subcommand and nonzero exit for a bare invocation.
- Added `initialise.py` and `init`: repository/branch/configured GitHub origin
  validation before writes, missing CLI warnings, a failing placeholder
  Makefile, and backlog setup. Only an unborn current branch or a single root
  Makefile commit gets the quick-start push behavior. Existing codebases get
  no code commit or push. Commit/push failures propagate Git's message and
  state-based reruns complete setup. Other staged files remain staged.
- Added executable `install.sh`: checks every prerequisite, refuses unsupported
  checkout paths, appends the quoted alias to `.bashrc` once, and warns without
  replacing an existing alias. Only temporary homes were used in verification.
- Updated README and backlog documentation with setup, prerequisites, product
  environment selection and usage. Updated harness invocation references in
  archived work items too, because the criterion's grep includes all `docs/`;
  each archive identifies this update, preserving recorded check output.
- Added nine unit tests for URL/target/path parsing and quick-start state
  transitions using real Git repositories. Updated three existing request
  assertions to compare rendered prompts with the resolved harness placeholder.
  No acceptance automation suite was added.

Checks and actual results:

1. The initial ordinary `uv run` failed before executing Python (exit 2):

   ```text
   error: failed to open file `/home/tarttelin/.cache/uv/sdists-v9/.git`: Read-only file system (os error 30)
   ```

   Subsequent commands used `UV_CACHE_DIR=/tmp/devteam-uv-cache`.

2. Foreign-product shadowing subprocess check, with a temporary Git repository
   containing `yaml.py` that exits with `shadowed`:

   ```text
   flags=['-P']: exit=0; stdout=''; stderr=''
   flags=[]: exit=1; stdout=''; stderr='shadowed\n'
   ```

3. Initial targeted run of initialisation, engines, runner and checkout tests:

   ```text
   Ran 40 tests in 4.649s

   OK
   ```

4. Additional request/publish/republish/check tests initially failed (exit 1):

   ```text
   AssertionError: False is not true
   ```

   Two failures were caused by raw-template `startswith` comparisons after
   introducing substitution; one caused three subsequent subtest errors:

   ```text
   IndexError: list index out of range
   Ran 28 tests in 7.057s

   FAILED (failures=2, errors=3)
   ```

   Updated those assertions to expect the resolved placeholder. The combined
   rerun including the request UI class stalled after progress dots and was
   interrupted (exit 130); it produced no final test verdict.

5. Final direct unit-test command (excluding the UI class):

   ```sh
   UV_CACHE_DIR=/tmp/devteam-uv-cache timeout 30s uv run python -m unittest tests.test_initialise tests.test_engines tests.test_runner tests.test_checkout tests.test_requests.Requests tests.test_publish tests.test_republish tests.test_check
   ```

   Exit 0, actual final output:

   ```text
   Ran 68 tests in 11.397s

   OK
   ```

6. A minimal `asyncio.run` / `asyncio.to_thread` diagnostic reproduced the
   sandbox async executor shutdown problem already recorded by STORY-010:
   `timeout 5s` exited 124. Actual output:

   ```text
   async worker completed
   ```

   The following `async shutdown completed` print was never reached. No
   application or test code was changed to bypass this environment problem.
   There is no full-suite or TUI pass claim; the full suite remains for the
   tester/runner as requested.

7. Foreign-product CLI smoke check using the documented prefix: `help` exited
   0 and printed descriptions for all six commands, `--product`, and all four
   backlog actions. Bare invocation exited 2:

   ```text
   devteam: error: the following arguments are required: cmd
   ```

   With a configured HTTPS GitHub origin redirected to a temporary local bare
   repository, first `init` exited 0:

   ```text
   Committed Makefile on main
   Pushed main to origin
   Backlog is set up at /tmp/tmp7xixz5sd/product/backlog
   ```

   Second `init` exited 0:

   ```text
   Product is already set up on main
   Backlog is set up at /tmp/tmp7xixz5sd/product/backlog
   ```

   Placeholder `make regression` exited 2, as intended:

   ```text
   regression unimplemented: wire up the product's checks
   make: *** [Makefile:5: regression] Error 1
   ```

   The tester argv contained:

   ```text
   Bash(uv run --project /home/tarttelin/projects/pyruby/dev-team python -P -m devteam *)
   ```

   Each of default/test, default/review, analysis/product-owner and the tester
   brief reported `contains harness command: True`.

8. Installer manual checks with temporary HOME: first run exited 0 and printed
   `Added dev-team alias to ~/.bashrc. Open a new shell or source ~/.bashrc.`
   Both runs warned that git `user.name` and `user.email` were not configured
   in that temporary home. Second run exited 0 with:

   ```text
   WARNING: dev-team alias already exists in ~/.bashrc; left unchanged
   ```

   `.bashrc` was byte-identical on rerun and the only home file created. The
   alias was:

   ```sh
   alias dev-team='uv run --project "/home/tarttelin/projects/pyruby/dev-team" python -P -m devteam'
   ```

   Copies in paths containing a space, `*` and `(` each exited 1 with the
   harness-path error and wrote no alias. A stub PATH without prerequisites
   exited 1, created no home files, and reported all missing commands:

   ```text
   Missing required prerequisite: uv
   Missing required prerequisite: git
   WARNING: claude is missing from PATH
   WARNING: codex is missing from PATH
   WARNING: gh is missing from PATH
   ```

9. `bash -n install.sh`, Python compilation of the changed configuration/CLI
   and initialisation modules, and `git diff --check` exited 0 with no output.
   The old bare-command grep over README/prompts/roles/config/docs, retired
   workspace grep excluding backlog/docs, home-resource grep over devteam,
   and pip/python3 grep over README all returned no matches (exit 1).

The fresh-computer walkthrough and live Claude allow-list behavior are human
criteria and have not been exercised here. No implementation work requires
additional customer input.

## Tests

All in `tests/test_launcher.py`, driven through `uv run --project <checkout> python -P -m devteam` (and `bash install.sh`) from temporary product repositories, with `origin` redirected to a local bare repository by `insteadOf` and the `claude` stub from `tests/stubs`. Run one with `uv run --project /home/tarttelin/projects/pyruby/dev-team python -P -m devteam check tests.test_launcher.Init.test_init_in_an_empty_repository_commits_pushes_and_sets_up_the_backlog` (any class or test name after `tests.test_launcher`).

- Shadowing, with and without `-P`: `ShadowingAndEntryPoint.test_product_modules_cannot_shadow_what_the_harness_imports`
- Subprocess backlog from a foreign product: `...test_launcher_from_a_product_outside_the_checkout_acts_on_that_products_backlog`
- `help` content and bare invocation: `...test_help_lists_every_command_and_backlog_action`, `...test_no_arguments_exits_nonzero`
- Product root versus harness root: `...test_locate_finds_the_product_backlog_while_harness_files_stay_in_the_checkout`
- Empty repository, TUI, no agent: `EmptyRepository.test_tui_opens_an_empty_backlog_and_starts_no_agent`
- Two products and one checkout: `Isolation.test_changing_items_in_one_product_leaves_the_other_and_the_checkout_alone`
- Missing engine / failing engine: `EngineFailure.test_missing_engine_command_is_reported_and_the_item_stays_put`, `...test_engine_exiting_nonzero_is_reported_and_the_item_stays_put`
- Agents: `AgentsReachTheHarness` (allow-list argv, rendered prompts and tester brief, the command running from a product, no bare command in checked-in files, refusal of an unsupported checkout path for `run`/`tui`/`init` with `help` unaffected)
- `init`: `Init` class, one test per criterion (empty repository, second run, after an earlier launch, the three origin forms, look-alike host, missing-command warnings, each refusal, tracked/untracked Makefile, identity and push reruns, existing codebase, unpushed work, differing origin commit)
- `install.sh`: `InstallScript` class (alias once and rerun, working alias, all missing prerequisites reported, required versus warning-only, only `.bashrc` written, unsupported paths, `bash -n`)
- Guards: `Guards` class (retired workspace, home directory, README pip/python3 and bare command)

The README/`docs/backlog.md` wording criteria are covered only for the bare-command and "(the workspace)" greps; the rest of the documentation criteria are read by the reviewer. The `[human]` criterion is not automated.

## Review

No blocking findings. Every criterion has code behind it and, apart from the documentation prose and the `[human]` criterion, a test that runs the real system (the harness's run: 216 tests, OK).

Minor points, none needing a revise:

1. `has_regression` (`devteam/initialise.py`) is a line heuristic. It treats `regression::` (a double-colon rule) and targets defined through includes or pattern rules as absent, so it can print the "no regression target" warning for a Makefile that works. It only warns, so it is cosmetic.
2. `init` acts on the repository top, not the current subdirectory. Running it from a subdirectory sets up the whole repository. This is reasonable, but the README does not say so.
3. `git config --get remote.origin.url` fails if `origin` has several URLs. That is treated as "no GitHub origin", which is a safe refusal.

Criteria satisfied, with evidence:

- Harness command (`config.harness_command`, `engines.build_argv`, `runner.render`, `Role.brief`): one derived value with `--project` and `-P`. It is substituted into the allow-list, prompts and tester brief, and it raises for unsupported characters. `cmd_init`, `run` and `tui` validate it before work, while `help`, `backlog` and `check` skip it. The bare-command grep over README, docs, prompts, roles and config is empty. Tests: `AgentsReachTheHarness`, `ShadowingAndEntryPoint`.
- `help` and bare invocation: every subparser has a help string, and `help` prints the top-level help followed by the backlog help. The `required=True` setting is kept, so a bare run exits 2. Tests: `test_help_lists_every_command_and_backlog_action`, `test_no_arguments_exits_nonzero`.
- `init` order and refusals: the repository, branch (not detached, not `devteam/*`) and GitHub origin are all checked before any write. The origin regex is anchored with `fullmatch` and reads `remote.origin.url`, so the `insteadOf` forms and the look-alike host are handled. Warnings cover missing `claude`, `codex` and `gh`.
- `init` commit and push: the quick-start state is defined on the current branch, so an unborn HEAD or a single root Makefile-only commit qualifies. It commits only `Makefile`, pushes only when `ls-remote` returns 2, reports "already set up" when the commit matches, and warns when it differs. The existing-codebase path commits and pushes nothing and prints the wire-up message. Tests: the `Init` class, one test per criterion. The base-resolves check is among them.
- `install.sh`: it reports every missing tool in one run, exits nonzero only for uv or git, never replaces an existing alias, refuses unsupported paths, and writes only `.bashrc`. Tests: `InstallScript`.
- Harness/product split, empty repository with TUI, isolation between two products, and missing or failing engine: `EmptyRepository`, `Isolation` and `EngineFailure` in `tests/test_launcher.py`, plus the product-root test.
- Documentation: README and `docs/backlog.md` give the alias route, `install.sh`, `init` behaviour and Requirements (including the Makefile environment point). "(the workspace)" is gone. The bare-command grep returns nothing.
- Guards: the workspace, home-directory and pip/python3 greps are covered by the `Guards` class.

Not proven, and rightly left to the `[human]` criterion: that `claude` honours an allow-list pattern containing a path, and the fresh-computer walkthrough.

The rewrite of the archived `docs/work-items/*` is not in the story as such. It follows from the criterion that greps all of `docs/`, and each archive is marked as updated, so I accept it.

## Test run

Run by the harness, 2026-10-07 20:46 UTC. Full output: `/home/tarttelin/projects/pyruby/dev-team/backlog/log/STORY-006/verify-20261007T204422450761.log`

Passed: `the project check`

```text
uv run python -m unittest discover -s tests
.................................................................................................................................................................................Executing <Task pending name='message pump Note()' coro=<MessagePump._process_messages() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/message_pump.py:571> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.106 seconds
.....Executing <Task pending name='screen_update' coro=<Timer._run_timer() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/timer.py:146> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.105 seconds
.....Executing <Task pending name="message pump Screen(id='_default')" coro=<MessagePump._process_messages() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/message_pump.py:571> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.111 seconds
Executing <Task pending name="message pump Screen(id='_default')" coro=<MessagePump._process_messages() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/message_pump.py:571> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.119 seconds
.......Executing <Task pending name='screen_update' coro=<Timer._run_timer() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/timer.py:146> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.139 seconds
.......Executing <Task pending name='message pump Header()' coro=<MessagePump._process_messages() running at /home/tarttelin/projects/pyruby/dev-team/.venv/lib/python3.13/site-packages/textual/message_pump.py:566> wait_for=<Future pending cb=[Task.task_wakeup()] created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/base_events.py:459> created at /home/tarttelin/.local/share/uv/python/cpython-3.13.7-linux-x86_64-gnu/lib/python3.13/asyncio/tasks.py:410> took 0.151 seconds
...............
----------------------------------------------------------------------
Ran 216 tests in 99.520s

OK
```
