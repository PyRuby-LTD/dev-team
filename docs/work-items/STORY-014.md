---
id: STORY-014
type: story
title: Keep run evidence out of the committed work item
parent: EPIC-002
workflow: default
step: publish
---
**As a** customer running dev-team in my own product repository
**I want** test output and tool output kept separate from the work item
**So that** the record committed under `docs/work-items` describes the story
without disclosing details of my computer or environment

## Context

The work item is both the record of a story and the only channel between
agents, so test output, commands as run and absolute paths accumulate in it and
are committed with it. They also reach GitHub, because the pull request body is
drawn from the item. That output is useful while a story is in flight and has
no value in the record. Run evidence should live in the backlog's uncommitted
log directory, with the item holding only the outcome.

## Acceptance Criteria

- [ ] **Given** the project check exits 0, **When** the harness records the
      test run, **Then** `## Test run` states that it passed, the exit code,
      the UTC time and the duration in seconds, and contains no check output,
      no absolute path and no fenced block; the full output is in
      `log/<id>/verify-<stamp>.log` in the backlog. (The verify step's
      transition stays `passed`.)
- [ ] **Given** the project check exits non-zero, **When** the harness records
      the test run, **Then** `## Test run` states that it failed with that exit
      code, the transition is `failed`, and the full output is in
      `log/<id>/verify-<stamp>.log` in the backlog and appears nowhere in the
      item. Nor does the item contain the log's path.
- [ ] **Given** the check times out or cannot be started, **When** the harness
      records the test run, **Then** `## Test run` says "timed out" or "could
      not be started" respectively and shows no exit code, even when the
      check could legitimately exit 124 or 127; the transition is `failed`; a
      `verify-<stamp>.log` is still written, holding the timeout or start
      error. A check that really exits 124 or 127 is recorded as failed with
      that exit code.
- [ ] **Given** a check whose output is not Python test output (for example
      output containing the text "OK", "FAILED" or "Traceback" in either
      direction), **When** the harness records the test run, **Then** the
      recorded verdict and transition depend only on the exit code.
- [ ] **Given** the implement, test and review steps, **When** the prompt is
      rendered after a check has run for the item, **Then** it contains the
      absolute path of the latest log written by the workflow's check step
      (`step.check`; `verify-<stamp>.log` in the default workflow) for that
      item, supplied as the prompt value `{{verify_log}}`; when no check has
      run yet it says so; and
      no prompt template under `prompts/` and no brief under `roles/` tells
      the agent to read test output from `## Test run` or to report or paste
      actual output (`prompts/test.md`, `prompts/review.md`,
      `prompts/implement.md` and `roles/implementer.md` change).
- [ ] **Given** any step run by an agent (analysis, challenge, implement, test,
      review, publish), **When** its prompt is rendered, **Then** the shared
      `PROTOCOL` text tells the agent: for a run of `dev-team check`, to cite
      the path that command prints (it has already saved the full output) and
      not to copy the output; to put any other command output it captures
      under `log/<id>/` in the backlog (the prompt value `{{evidence_dir}}`,
      the absolute directory); to name checks and their results in the item
      without pasting output; and to write paths relative to the repository
      and the harness command as `dev-team`. `prompts/test.md` requires that,
      on `defect`, the item gives the relative path of the failing run's log
      and what the test expected, so that the implementer, whose
      `{{verify_log}}` predates that run, can find it.
- [ ] **Given** `dev-team check` is run, **When** it prints where the full
      output went, **Then** the path is relative to the checkout (for example
      `backlog/log/check/<stamp>.log`), so that pasting the line into the item
      does not trip the copy guard; the log is written to the same place as
      before.
- [ ] **Given** an item body, **When** the runner would copy it to
      `docs/work-items` (the `record = true` step, today only the publisher),
      **Then** a line trips the guard if it contains, with a boundary before
      it (start of line, `file://`, or any character outside `A-Za-z0-9._-/`,
      which covers whitespace, quotes, backticks, brackets, `(`, `=`, `:`, `,`,
      `|`, `@` and shell redirection), any of: `str(self.checkout)`; `str(config.ROOT)`; `sys.executable`;
      `sys.prefix` or `sys.base_prefix` (each only when it has two or more
      path components and is not `/usr/local`, so a system Python's `/usr`
      never trips); a `/home/`, `/Users/` or `/root/` prefix followed by at
      least one character of `A-Za-z0-9._-`; `/tmp/pytest-of-` followed by at
      least one such character (pytest's temporary directory, which carries the
      login name). A literal value must also end at a path
      boundary (end of line, `/`, or a character outside `A-Za-z0-9._-`). A
      tripped line is masked as defined in the masking criterion below, in the
      copy only: the copy is written and the step carries on, the item in
      `backlog/` is not altered, and `report` is given a message naming the
      line numbers (not their content) and saying they were masked. The
      copy then trips nothing when the guard is run over it. A body that trips
      nothing is copied byte-for-byte as today.
- [ ] **Given** a line that trips the match rule, **When** it is masked,
      **Then** the whole path is replaced, meaning the run of
      `A-Za-z0-9._-/` characters that begins at the match: a path beginning
      with `str(self.checkout)` becomes the remainder relative to the checkout
      (`.` when nothing follows), and any other path becomes `<path>`. The rest
      of the line is untouched, so prose, quoting and punctuation around it
      survive. Masking is applied until the line no longer trips and is
      idempotent: masking masked text changes nothing. Masking applies to the
      item body, which is Markdown; the guard never reads or alters product
      code, which the customer judged too risky to alter.
- [ ] **Given** any commit to the `devteam-backlog` branch (every route goes
      through `Repository.commit`, which stages the whole tree, and the guard
      is installed on every `Repository` the CLI builds: `cmd_backlog`,
      `cmd_run`, and both objects in `cmd_tui`, since the TUI's commits for
      the customer's answers, notes, moves and captures are made by a
      different object from the runner's, and `backlog capture --file` run by
      an agent is a separate process. The guard is built from `self.checkout`,
      `config.ROOT` and `sys`; a value that is absent, such as the checkout
      outside a git repository, contributes no pattern. Routes: an accepted
      reply's transition, the `<id>: <step> failed` commit from `run_item`
      after a non-zero exit, a missing or invalid `TRANSITION` line or changed
      front matter, and a commit made for another item while an agent is
      still writing, and `rejected` writing `## Pull request feedback` through
      `write_body`, which is masked like any other text), **When** the commit is made, **Then** the same match
      rule is applied to every line of every text file that the commit would
      stage and that differs from the last commit, whatever its name or
      directory (an item, a file beside it, `brief.md` or any other file in
      the backlog root; a file that is not valid UTF-8 is skipped, a named
      gap), lines already committed, such as the home-directory paths in
      earlier items, never tripping. In a Markdown file under the item
      directories, front matter (the lines between the opening `---` and the
      next `---`, title included) is not checked and is never altered; in any
      other file, and in an item with no closing `---`, the whole file is
      checked. Each file with a trip is first saved, unmodified, to
      `log/<id>/unmasked-<stamp>.md` in the backlog (uncommitted, `<id>`
      being the file stem of an item file, which is its id even when the
      agent has damaged the front matter) or, for any other file, to
      `log/unmasked/<stamp>-<name>` where `<name>` is its path relative to
      the backlog with `/` replaced by `__`, then rewritten in the working tree with the
      tripped lines masked and its front matter unchanged, and only then
      staged. The agent's step is not otherwise affected: an accepted reply
      carries on to its transition. The `Repository` is given the guard and a
      notice sink, and the message names the line numbers (which refer to the
      saved file) and the saved file relative to the checkout. The sink is, per
      site: the runner's `report` for both runner repositories (`cmd_run` and
      the runner half of `cmd_tui`); a Textual `notify` for the TUI's own
      repository; a printed line on standard output for `cmd_backlog`, so that
      `backlog capture --file` run by an agent tells the agent. A test asserts
      the message through `main` for the capture, and one TUI test asserts the
      notification when the customer's typed note trips. Masking happens inside `Repository.commit`, so it follows
      the product-branch commit in `invoke` and falls inside
      `repository.transition`; it never touches the product branch. The
      property tested is on
      what is committed: no commit on the backlog branch contains the
      offending text, whether the step succeeded, the engine exited non-zero
      after writing it, the reply was malformed, the agent edited a different
      item, or another item was captured, answered or moved meanwhile. Where
      nothing trips, behaviour is as today and no `unmasked-` file is written.
      Tests use a fake engine and assert on `git log -p` of the backlog branch
      for at least: success; engine writes a tripping line then exits
      non-zero; engine writes it to a different item; a second item is
      captured while the engine is running, the capture and commit made
      through a second `Repository` on the same root (as the TUI does); the
      engine writes a tripping line to a non-Markdown file beside the item and
      to a file in the backlog root, with the unmasked copies found under
      `log/unmasked/`; the engine breaks the item's front matter and
      writes a tripping line, the saved file being named by the file stem; and
      `backlog capture --file` with a tripping body driven through `main`;
      and `rejected` with a GitHub feedback fixture carrying a home-style path
      built at run time.
- [ ] **Given** the harness writes `## Test run` (`Runner.verify`), **Then**
      the text it writes cannot contain a path of the machine: a test asserts it with the checkout, harness root and
      interpreter paths all set to values that would trip the match rule.
- [ ] **Given** the guard's match rule, **Then** a test table shows that
      lines of these shapes trip: the checkout path after `Full output: `; a
      home-directory path in backticks; one after `cwd=`; a root-user path at
      the start of a line; a home-directory path
      after `> `, after a comma, after `[`, after `|`, after `@` and inside
      `file://`; a pytest temporary directory (`/tmp/pytest-of-<name>/...`);
      and the running `sys.executable`. Routes such as `GET /api/orders` and
      `/media/index.html` do not trip, whereas a route whose first segment is
      `home`, `Users` or `root` followed by a name (`GET /home/<name>`)
      does trip and is masked, which is the chosen behaviour. The test builds the real
      strings from a placeholder name at run time; this item writes them with
      `<name>` so that it does not trip itself. For each tripping row the test
      also asserts the masked line (the checkout path followed by a
      sub-path becomes that sub-path; the others become `<path>`), that the
      surrounding text is unchanged, that the placeholder name is absent from
      every masked line, and that the masked line trips nothing.
      Lines that do not trip:
      `src/root/app.py`, `tests/root_test.py`,
      `templates/home/index.html`, `https://example.com/home/news`,
      `#!/usr/bin/env python` (including when `sys.prefix` is `/usr`),
      `/dev/null`, and the example lines in this item that write
      `/home/<name>`, `/Users/<name>`, `/root` and `/home/` without a real
      name. The guard run over the whole body of this item trips nothing, so
      that STORY-014 can itself be published; a reviewer runs the guard
      function over the body to confirm it.
- [ ] **Given** the guard is implemented, **Then** it obtains its values only
      from `self.checkout`, `config.ROOT` and `sys`, and
      `tests/test_launcher.py::test_nothing_in_the_harness_reads_the_home_directory`
      still passes.
- [ ] **Given** the publisher's prompt, **When** it is rendered, **Then** it
      tells the publisher not to put absolute paths, home directories or
      command output in the pull request body (the copy guard does not cover
      the body, which the agent writes).
- [ ] **Given** a story run from start to publication, **When** the product
      repository is inspected, **Then** no file from `backlog/log/` is tracked
      on any branch of it.
- [ ] **Given** the records of stories already completed, **When** this story
      is merged, **Then** each is byte-identical to its state before the story.
- [ ] [human] Run a story end to end in a product repository and confirm that
      the committed record and the pull request body contain no home directory
      or interpreter path.

## Notes

- The harness must treat check output as opaque. Products may be written in
  any language; only the exit code can be relied on. Interpreting a failure is
  the agents' job.
- The check's output is already written to `log/<id>/verify-<stamp>.log` in the
  backlog, which is git-ignored. The change for the harness's own run is mainly
  what goes in the item and how agents are pointed at the log.
- Agents still need the absolute harness command in their prompt in order to
  run it. The requirement is about what they write in the item.
- The prompt changes are instructions and will sometimes be ignored; the
  checks on the agent's edit to the item and at the copy step are the
  guarantee, for what the harness sees before it commits. History already
  pushed is not rewritten. It uses values the harness already holds,
  so the existing guard against reading the home directory stands.
- On `defect`, the tester is currently asked to record the failing test's
  output in the item. That becomes the failing test, what it expected and the
  relative path of the log that `dev-team check` printed, with the output left
  in that log.
- A tripped guard masks the path and carries on, rather than failing the step
  or sending the item back to the agent (question 3: failing does not meet
  the brief, returning creates loops, masking is acceptable for Markdown).
  The unmasked body is kept uncommitted under `log/<id>/` so nothing is lost.
- Question 4: the customer chose not to block on or refuse GitHub review
  comments. The text `rejected` writes into `## Pull request feedback` goes
  through `write_body` and so is masked like any other item text; nothing is
  exempted. A reviewer's quoted route with a `home` first segment would reach
  the implementer as `<path>`; the unmasked text is in `log/<id>/`.
- STORY-006 counts as already played; its committed copy keeps its current
  content unless it is sent back through the workflow.
- Limitation, chosen: a URL route whose first segment is `home`, `Users` or
  `root` followed by a name cannot be told from a home directory, so in an item
  it becomes `<path>`. To keep such a route, write it with its host or without
  the leading slash. Routes with any other first segment are left alone. Front
  matter, including the title, is not checked, so a path typed there is
  committed.
- Out of scope: rewriting git history, altering completed records, and
  scanning for secrets.

## Questions

1. The copy guard rejects the checkout path and the harness root, the only
   machine-specific values the harness holds without reading the home
   directory. It would not stop other absolute paths in the item, such as an
   interpreter under the home directory (STORY-013 has the uv-managed Python
   in its record). Is checkout-and-harness-root enough, with the [human]
   criterion covering the rest? Or should the guard also reject the running
   interpreter's path and prefix, or any line that looks like an absolute
   path? The last is the strongest but would also reject legitimate mentions
   such as `/dev/null` in an item.

   **Answer:** The guard is the last line of defense. The key requirement is that paths on the user's computer are not leaked. That could be because they are masked or because they get written to files that don't get committed. The key part is they don't get into git.

2. Every edit to an item is committed to the `devteam-backlog` branch in
   `backlog/`, which `docs/backlog.md` tells you to push, and that branch
   already holds home-directory paths in several items. You said the key part
   is that paths do not get into git. Does that include the `devteam-backlog`
   branch, or only the committed record under `docs/work-items` and the pull
   request? If it includes the backlog branch, the check would run when the
   harness accepts each agent's edit to the item, for every agent step. What
   should a trip do there: stop for a hand edit, send the item back to the
   agent that wrote it, or mask the offending text automatically (the checkout
   path becomes a relative path; other paths become a placeholder)?

   **Answer:** I'm struggling to think of a good reason why a story should legitimately contain an absolute path, given it's intended to run on different computers, checked out in different paths, so inclusion of a fully qualified path should never be okay, even (or especially) in devteam-backlog.

3. When an agent writes an absolute path into an item, should the harness
   (a) fail the step and discard the agent's edit, leaving you to restart or
   retry it, (b) send the item back to the same agent with the offending lines
   pointed out, up to a fixed number of times, or (c) replace the path with a
   placeholder and carry on? In every case the rejected body is saved
   uncommitted under `log/<id>/` so you can read it. Option (a) is what the
   criteria currently assume.

   **Answer:** Option a) does not meet the brief. Option c) risks making things hard to read. Option b) creates yet more loops, probably not necessary. For markdown docs, option c) is probably okay. For code, it's potentially going to break stuff so I'm unsure whether to pick option a) or option b).

4. The runner copies the text of GitHub review comments into `## Pull request
   feedback`, which is committed to the `devteam-backlog` branch. A pasted
   traceback from a reviewer could contain a home-directory path. Should the
   harness refuse to record feedback that trips the path check (the item stays
   at its step until the comment is edited on GitHub and the step retried), or
   record it as written and leave it uncovered?

   **Answer:** If it's in the PR comments, then copy it as is. The idea that it would contain absolute paths in a review is pretty unlikely so it's an edge case I can live with for now.

5. A tripped path is now masked rather than failing the step, so a false trip
   costs one word. Should the guard mask (a) only home directories and the
   harness's own checkout, install and interpreter paths, accepting that other
   absolute paths, such as a temporary directory containing your login name
   (pytest's, for example), a mount under the media directory, or a CI
   workspace, are committed; or (b) every absolute path, accepting that a URL
   route or the null device written in an item becomes `<path>`, including in
   acceptance criteria that describe a web product's routes?

   **Answer:** Is there a way of separating url paths from filesystem paths? Stories related to REST apis will need to define paths which are valid, whereas stack traces or paths to tool calls expose local computer specifics. This feels like it makes it impossible to mask all paths and limits me to masking things under the home directory, i.e. checkout paths.

## Analysis

The acceptance criteria and Notes govern. The round-by-round responses below
are history: where they mention raising `StepFailed`, a restore-and-fail
recovery, an `rejected-<stamp>.md` file, running the check in `invoke` before
`transition`, "only the copy guard is enforced" or checking only the lines a
step added by a separate mechanism, the criteria supersede them. The guard is
masking inside `Repository.commit` (diff lines against the last commit) plus
masking of the copy to `docs/work-items`; saved files are
`log/<id>/unmasked-<stamp>.md`.

Round seven: pull request feedback is not exempt (see Notes); the notice sink
is named per site in the backlog-commit criterion; a home directory that is
not at the filesystem root is a named gap (below).

The premise holds. Question 2 needs the customer's answer; the rest is stated
as assumptions.

What exists today:

- `Runner.verify` (`devteam/runner.py`) writes `## Test run` containing
  `Full output: <absolute log path>` and `checks.summary(...)`, which embeds the
  last 60 lines of check output in a fenced block. That is the leak. The log
  itself is already at `backlog/log/<id>/verify-<stamp>.log` and is git-ignored
  (`ensure_backlog` writes `log/` to the backlog's `.gitignore`), so the
  evidence location needs no new storage.
- `check.run` returns `(code, output)` and encodes a timeout as 124 and a
  failure to start as 127. A real exit of 124 or 127 is indistinguishable, so
  the "says which of the two happened" criterion cannot be met without the
  result carrying an explicit status. It also does not time the run. Runner
  tests inject a fake `check=` returning `(code, output)`
  (`tests/test_check.py`), so changing the return shape touches them and
  `cmd_check` in `devteam/cli.py`.
- The "only the exit code" criterion is already true of the transition
  (`code == 0`); the risk is only in the summary text, which goes away with the
  output.
- `prompts/test.md` tells the tester to read a failure in `## Test run`, and
  `prompts/review.md` calls that section "the only test output you should
  trust". `prompts/implement.md` asks for "the actual output of the checks"
  under `## Implementation`, and `prompts/test.md` asks for the failing test's
  output on `defect`; both change. The analysis, challenge and publish prompts
  and the `roles/*.md` briefs carry no instruction about paths or output.
- `Runner.invoke` is the only place the item is copied to `docs/work-items`
  (roles with `record = true`; only `publisher`). The copy happens before the
  agent starts, so the guard belongs just before `copy.write_bytes` and raises
  `StepFailed`, which `run_item` already turns into "not retried until
  restart" with the item left at its step.
- The "guard against reading the home directory" is
  `tests/test_launcher.py::test_nothing_in_the_harness_reads_the_home_directory`,
  which greps `devteam/` for `Path.home`, `expanduser` and `environ['HOME'`.
  The guard must use `self.checkout` and `config.ROOT` only.
- Existing committed records contain `/home/` paths (BUG-001 26 lines, BUG-002
  9, STORY-006 9, others fewer). They stay as they are.

Response to the challenge:

- Finding 1: `cmd_check` is brought into scope (new criterion), since its
  printed absolute path is the commonest source of a trip. Recovery after a
  trip is now stated in the guard criterion.
- Finding 2: `roles/implementer.md` lines 14-15 ("report their actual output")
  conflict with the new rule; it is added to the files that change and the
  criterion covers prompts and role briefs.
- Finding 3: asked as question 1. The customer answered that the guard is the
  last line of defence and the requirement is that no path on the user's
  computer reaches git, by masking or by keeping it in uncommitted files. The
  guard criterion is widened accordingly (see below).
- Finding 4: steps are named and two prompt values added: `verify_log` (latest
  `verify-*.log`, or text saying no check has run) and `evidence_dir`
  (`<backlog>/log/<id>`). `invoke` already builds the `values` dict, and
  `PROTOCOL` reaches every agent step, so the shared instruction goes there.
- Finding 5: `check.run` already writes the log in every case, including
  timeout and failure to start; the wording is fixed in the criteria as
  "could not be started".

What would change:

- `devteam/cli.py`: `cmd_check` prints the log path relative to the checkout.
- `roles/implementer.md`: drop the instruction to report actual output.
- `devteam/check.py`: result carries status (`passed`, `failed`, `timed out`,
  `not started`), exit code and duration; `summary` is replaced by a short
  paragraph with no output and no path.
- `devteam/runner.py`: `verify` records that paragraph; `invoke` runs the copy
  guard and supplies the latest verify log path (or "none yet") as a prompt
  value for steps that use it.
- Prompts: `test.md`, `review.md`, `implement.md` as above, plus one shared
  instruction in `PROTOCOL` (or per prompt) for every agent that edits the
  item: command output goes under `log/<id>/` in the backlog, the item names
  checks and results only, paths are relative to the repository, and the
  harness command is written `dev-team`.

Response to the second challenge:

- Finding 1: confirmed against the code. `Repository.write_body` commits every
  item edit to the `devteam-backlog` branch, which the documentation tells the
  customer to push, and local and origin copies of that branch already hold
  home directories. Whether that branch counts as "git" is the customer's
  decision: question 2. Until answered, the criteria cover only the copy to
  `docs/work-items`, and that guard is not a guarantee about git.
- Finding 2: the match rule is now stated in the guard criterion, with a test
  table. Home prefixes need a following name, so prose such as `/root` or
  `/home/` alone does not trip, and the boundary before the match keeps
  relative paths and URLs clear. System-directory prefixes are excluded.
  Residual: a bare route whose first segment is a home segment would trip, costing one
  hand edit.
- Finding 3: folded into question 2.
- Finding 4: the pull request body is covered by prompt wording only. A
  post-publish check would need a `gh pr view` call and is not proposed; the
  [human] criterion covers one run.

Response to question 2 (customer: an absolute path should never be in an
item, "even (or especially) in devteam-backlog"). The restore-and-fail
recovery described here is superseded by the response to questions 3 and 4
below; the code analysis stands:

- The backlog branch is in scope. Code check: an agent edits the item file in
  `backlog/` directly; the first commit of that text is `Repository._transition`
  (`devteam/backlog.py`) after the reply is accepted in `Runner.invoke`, and on
  any failure `run_item` calls `repository.commit("<id>: <step> failed")`,
  which commits whatever is in the working tree. So the check must run in
  `invoke` after the reply and front matter checks and before
  `repository.transition`, and a trip must restore the file, otherwise the
  failure commit publishes the text anyway. The restore uses the body held in
  `record` from before the step, so no new storage is needed.
- Scope: only lines added by the step are checked. Otherwise every item that
  already holds a home directory (BUG-001 and others) would fail on any
  re-run. The copy to `docs/work-items` still checks the whole body, because
  that is what is published.
- Other writes to the backlog: `Runner.verify` and `rejected` write harness
  text, and `transition` notes are the customer's. `verify` is made path-free
  by construction (criterion added). The customer's own typed notes and
  questions are not checked.
- Not achievable and not claimed: history already pushed (`origin/devteam-backlog`
  holds home directories in earlier items) is not rewritten, and an agent's
  path in a commit made before the runner sees it (an agent that commits to the
  backlog itself) is not caught. The agent's sandbox usually cannot write
  `.git`, as the comment in `invoke` notes.
- The customer did not choose between stopping, returning to the agent and
  masking. The assumption is restore-and-fail: it never commits the text,
  cannot loop, and loses only one step's edit to the item, which the
  agent redoes once the runner restarts. Masking is not used because a home
  path replaced by a placeholder alters meaning silently, and the match rule
  can false-trip on a route whose first segment is a home segment. If the customer wants
  masking or return-to-agent, say so when they review.
- The match rule is unchanged. Rejecting "any absolute path" is not adopted,
  since `/dev/null` and `/usr/bin/env` are not facts about the customer's
  machine; the criterion's intent (paths on the user's computer) is covered by
  the home prefixes and the harness's own checkout, root and interpreter
  values.

Response to the third challenge:

- Finding 1: addressed above and by the new backlog-edit criterion.
- Finding 2: already stated in the match-rule and test-table criteria, which
  include this item's own `/home/<name>`, `/Users/<name>`, `/root` and `/home/`
  lines, relative paths, URLs and `/usr/bin/env` under `sys.prefix` of `/usr`.
- Finding 3: folded into the assumption above rather than asked again, since
  the customer's answer to question 2 did not pick one.
- Finding 4: unchanged; the pull request body is covered by prompt wording and
  the [human] criterion only.

Assumptions:

- The guard's values come from `self.checkout`, `config.ROOT` and `sys`, and
  its patterns do not contain `Path.home`, `expanduser` or `environ['HOME'`,
  so the existing home-directory test stands.
- A trip masks rather than failing, on the backlog edit and on the copy alike
  (see the response to questions 3 and 4 below; this replaces the earlier
  restore-and-fail assumption).
- A generic "any absolute path" rule is not used, as it would reject
  `/dev/null` and similar harmless mentions. Home-style paths elsewhere on the
  machine (for example `/opt/<name>` or a mounted volume) are not detected; the
  human criterion covers those.
- The latest log is the highest-sorting `verify-*.log` in `log/<id>/`, found at
  render time, so it survives a runner restart.
- A flag with the path attached directly, such as a compiler include flag
  followed at once by a home path, is not detected, because the character
  before the path is a letter. This is a named gap; the human criterion
  covers it.
- Agents' own `dev-team check` runs write to `log/check/<stamp>.log` and
  print that path; they are not the "latest test run" and are not changed.
- The agents' instruction to write command output to the evidence location is
  advisory (stated in the item's Notes); only the copy guard is enforced.

Response to the fourth challenge:

- Finding 1: recovery is now asked on its own as question 3. Whatever the
  answer, the rejected body is saved to `log/<id>/rejected-<stamp>.md`
  (uncommitted) and named in the message, and the criterion fixes the order:
  the check runs before the product-branch commit in `invoke`, so a tripped
  step leaves the agent's code uncommitted in the checkout and changes nothing
  in git.
- Finding 2: confirmed; the must-trip examples and the bare-route mentions are
  rewritten so the item trips nothing, and the table criterion says so.
- Finding 3: boundary widened to any character outside `A-Za-z0-9._-/`, plus
  `file://`; shapes added for redirection, comma, bracket, pipe, `@` and
  `file://`. The attached-flag form is a named gap in the Assumptions.
- Finding 4: confirmed. `rejected` writes other people's text and is not
  guarded; asked as question 4. The transition-note half of the path-free
  criterion is dropped, since the harness writes no such note.
- Finding 5: both guard criteria now say restarted or retried.

Response to questions 3 and 4 (customer answers):

- Question 3: the customer ruled out failing the step, called returning to the
  agent a source of extra loops, and accepted masking for Markdown while being
  unsure for code. The guard only ever touches the item body, which is
  Markdown, and never product code, so masking applies. Recovery is therefore
  mask and carry on. This also removes the finding-1 concern that a false trip
  on a route costs a whole agent run: the worst case is a masked word in the
  item, with the original in `log/<id>/unmasked-<stamp>.md`. The earlier
  restore-and-fail text and the "pending question 3" caveats are removed.
- Masking is defined by a criterion of its own: the whole path is replaced,
  the checkout path becomes a relative path, anything else becomes `<path>`,
  and it is idempotent. At the copy it masks the copy only; the item in the
  backlog is left as the agent or customer wrote it, so earlier lines are not
  rewritten. The agent-edit check still looks only at lines the step added.
- Residual: masking is lossy, so an item that says where something lives
  loses that for a path under the home directory. Acceptable, as the customer
  prefers that to leaking.
- Question 4: feedback is copied as written; recorded in Notes as not covered.
  A pasted path there reaches the publish copy, where it is masked, but the
  backlog branch holds it as written.

Response to the fifth challenge:

- Finding 1: confirmed against the code. `Repository.commit` calls
  `git.commit_all` with no paths, and `run_item` commits after any
  `StepFailed`, so an unaccepted reply, a concurrent TUI commit or an edit to
  another item all stage unchecked text. The guard criterion is restated as a
  property of what `Repository.commit` stages, with the masking done there
  (the one place all routes meet) and tests for each route. This supersedes
  the earlier "customer's own typed notes are not checked": their lines are
  masked too, consistent with the answer that a path should never be in
  git, and the unmasked text is kept under `log/`. Residual: masking rewrites
  a file an agent may still be writing; a later write by the agent can
  reintroduce the text, which the next commit masks again.
  Implementation note: `Repository` needs the guard passed in (a callable),
  since it holds no checkout or interpreter values itself.
- Finding 2: asked as question 5. The match rule, table and does-not-trip list
  stay as they are until answered.
- Finding 3: accepted. The drive-letter form is dropped (the installer is
  bash-only and nothing the customer said asks for Windows), and the table
  asserts the placeholder name is absent from every masked line.
- Finding 4: `{{verify_log}}` is defined as the latest log of the workflow's
  check step; in the default workflow that is `verify-<stamp>.log`.

Response to question 5 (customer answer) and the final challenge:

- A URL route and a filesystem path cannot be told apart by their text:
  `/home/<name>` could be either. So no general "every absolute path" rule; routes
  in acceptance criteria are left alone. The customer's reading, that masking
  is limited to things under the home directory and the checkout, is adopted:
  option (a). The one addition is `/tmp/pytest-of-<name>`, which is
  unmistakably a filesystem path carrying a login name and appears in failing
  test output; it is in the match rule and the table.
- Still undetected, and named: other temporary directories, mounts under the
  media directory, CI workspaces, a second checkout outside the home
  directory, and a home directory not at the filesystem root (for example
  `/var/home/<name>` on image-based Fedora, or `/mnt/c/Users/<name>`), unless
  it lies under the checkout, harness root or interpreter. The [human] criterion covers them.
- Challenge findings 1, 3 and 4 were addressed in the previous round (guard
  restated as a property of `Repository.commit`; drive-letter form dropped and
  the placeholder name asserted absent; `{{verify_log}}` tied to `step.check`).
  Finding 2 is resolved by the customer's answer.

How the criteria are checked: the first five and the prompt criteria by runner
tests with a fake check and a rendered prompt; the guard by runner tests with a
fake engine, asserting that a tripped body is committed masked, that the
unmasked file exists under `log/<id>/`, that `git log -p` on the backlog
branch contains no tripped text, and that the copy under `docs/work-items`
is masked; the byte-identity criterion by `git diff main -- docs/work-items`
being empty for every record that existed before the story.

Response to the sixth challenge:

- Finding 1: confirmed in `devteam/cli.py` (`Repository(` at lines 23, 54 and
  66, the last twice). The guard criterion now requires it on every
  `Repository` the CLI builds, says absent values contribute no pattern, and
  adds tests through a second `Repository` and through `main`.
- Finding 2: accepted without a question. The limitation is in Notes, the table
  asserts that such a route trips, and the earlier "one hand edit" wording is
  superseded: under masking a route with a home-style first segment is masked
  and cannot be kept except by writing it with its host or without the leading
  slash. Routes with other first segments are left alone.
- Finding 3: the example in the question 5 response now uses `<name>`; the
  match rule run over this file finds nothing.
- Finding 4: ordering clause replaced; masking is in `Repository.commit` only.
- Finding 5: front matter is excluded and named in Notes; an absent checkout
  contributes no pattern.

Response to the eighth challenge:

- Finding 1: confirmed against the code. `git.commit_all` runs `git add -A`
  with no paths from `Repository.commit`, and the backlog's `.gitignore` holds
  only `log/`, so files outside the item directories are staged unread. Option
  (a) is adopted: the match rule runs over the new lines of every text file the
  commit stages, with unmasked copies of non-item files under
  `log/unmasked/`. Option (b) was not taken because it would change what the
  branch tracks and leave the root files already on it unexplained. Tests for
  a non-Markdown file beside the item and a file in the backlog root are added.
  Named gap: a binary file (not valid UTF-8) is not read.
- Finding 2: adopted as the first fix. `PROTOCOL` tells agents to cite the path
  `dev-team check` prints and to use `{{evidence_dir}}` only for other output;
  `prompts/test.md` requires the failing log's relative path on `defect`.
  `check` is not changed to write under `log/<id>/`.
- Finding 3: settled in the criterion: the id is the file stem, and a file with
  no closing `---` is checked whole.

## Challenge

Verdict: sound. This is the ninth round. The eighth round's three findings are
answered in the criteria, and each fix was checked against the code. A
competent engineer could build this as written and a reviewer could tell
whether they had. (The eighth challenge's text is replaced by this one; the
analyst's response to it now closes the Analysis above.)

Checked this round:

- The guard now reads what the commit stages. `Repository.commit` is the only
  caller of `git.commit_all` on the backlog (`devteam/backlog.py`), reached
  from `create`, `write_body`, `_transition` and the failure commit in
  `run_item`; the one other backlog commit is the first `.gitignore` commit in
  `ensure_backlog`, which holds no agent text. The criterion covers every text
  file staged, names where a non-item file's unmasked copy goes, and adds the
  two tests asked for. The backlog `.gitignore` still holds only `log/`, so
  both save locations are uncommitted.
- `PROTOCOL` and `prompts/test.md` now agree with what `dev-team check` does:
  cite the printed path, use `{{evidence_dir}}` for other output, and give the
  failing log's path on `defect`. `workflows/default.json` confirms `defect`
  goes to `implement` with no check between, which is the case that wording
  exists for.
- The file stem as the id, and the whole-file check for an item with no
  closing delimiter, settle the broken-front-matter case.
- An equivalent of the match rule run over this item's body finds nothing, and
  the body names neither the checkout nor the harness root, so the item can be
  published under its own guard.
- The README's account of the check and of `## Test run` stays true after the
  change; no documentation edit is missing from the item.

Not blocking. For the customer to read before playing; none needs rework:

1. **Agents' commits to the product branch are not checked, and Notes do not
   list that.** `Runner.invoke` commits whatever the agent left in the checkout
   (`<id>: <step> by <role>`), and the criteria say the guard "never touches
   the product branch". Answer 3 was unsure between failing and returning to
   the agent for code; the item does neither, on the ground that the guard
   only handles item text. That fits the story's title and stated outcome, and
   no tracked product file in this repository holds a home-style path outside
   `docs/work-items`, so there is no evidence the route leaks today. It is
   still a limitation the customer is accepting: a line under "Out of scope"
   would say so, and a separate story is the place for it if it is wanted.
2. **Pull request feedback is masked, where answer 4 said to copy it as is.**
   Notes state this plainly and it follows answer 2. The cost is one word lost
   from a reviewer's quoted path, with the original kept under `log/`.
3. **"Differs from the last commit" is not defined for a moved line.** Under a
   line diff a section that moves counts as new, so an old path in it would be
   masked. The result is more masking, never less, so either reading meets the
   tested property.
4. **The item is large.** It has two separable halves: the test-run record
   with its prompts, and the guard. Nothing requires them to ship together,
   and an implementer may sensibly take them in that order.

## Implementation

Addressed all five review findings:

- Both tests that read the mutable story body now use a fixed acceptance
  criteria fixture, so a generated Test run section cannot change their input.
- Replaced the two curly apostrophes in the tester prompt with ASCII quotes.
- Commit masking now enumerates tracked changes against HEAD and untracked,
  non-ignored files. It does not read or run git show for unchanged files.
  Renames, staged and unstaged edits, deleted files and an unborn branch are
  covered by direct unit checks with real git repositories.
- Saved-log notices use a relative path even when the backlog is outside the
  checkout. Publication-copy notices now give file line numbers.
- Replaced the legacy embedded Test run output with the outcome, UTC time and
  duration from the latest workflow check. Its original full output remains
  in the existing ignored verify log. The runner will perform the next
  workflow verify; no commits or front-matter changes were made here.

The existing outcome-only check records, evidence prompts and path masking
remain in place. Completed records are unchanged. The human end-to-end check
remains for the customer.

Checks and results (full captured output is in the evidence logs):

- Direct unit checks for evidence, check outcomes, runner and launcher guards:
  36 tests passed, exit 0. Log:
  `backlog/log/STORY-014/revision-unit-passed.log`.
- Existing publication-copy and capture guard checks: 7 tests passed, exit 0.
  Log: `backlog/log/STORY-014/revision-existing-tests.log`.
- Project target `make regression` selecting those unit modules, launcher
  guards and launcher harness-command checks: 41 tests passed, exit 0, using
  a writable temporary uv cache. Log:
  `backlog/log/STORY-014/revision-project-check.log`.
- Initial direct run including the full launcher module reported failures
  and stalled in its existing empty-backlog TUI check; interrupted, exit 130.
  Log: `backlog/log/STORY-014/revision-unit.log`.
- Isolated launcher diagnosis with the default uv cache: 5 tests ran, 2 failed,
  exit 1 because the sandbox makes that cache read-only. Those checks pass
  with the temporary cache in the project run above. Log:
  `backlog/log/STORY-014/revision-launcher-default-cache.log`.
- One focused run named a nonexistent launcher test class: 33 checks passed
  and the loader reported 1 error, exit 1. Corrected the selection for the
  passing direct run above. Log:
  `backlog/log/STORY-014/revision-focused.log`.
- Latest workflow log was read: its full suite passed, exit 0, with 272 tests.
  The full suite was not repeated in this implementation step.
- Final whole-item masking check, fixture masking check, ASCII prompt check,
  unchanged completed-records check and git whitespace check: passed, exit 0.
  Log: `backlog/log/STORY-014/revision-final-checks.log`.

## Tests

All in `tests/test_run_evidence.py`, which starts the harness as a process
(`python -m devteam`) with stand-in `claude`, `codex` and `make` executables on
PATH (`tests/stubs/scripted` is the engine stand-in, driven by a JSON plan) and
the offline `gh` stub. Run one test with
`dev-team check tests.test_run_evidence.<Class>.<test>`.

- Passing check recorded as outcome only: `TestRunRecord.test_passing_check_is_recorded_as_an_outcome_with_the_output_in_the_log`.
- Failing check, output and log path absent from the item:
  `TestRunRecord.test_failing_check_is_recorded_as_failed_with_its_exit_code_and_no_output_or_log_path`.
- Timeout, cannot be started, real 124 and 127:
  `test_a_check_that_times_out_is_recorded_without_an_exit_code`,
  `test_a_check_that_cannot_be_started_is_recorded_without_an_exit_code`,
  `test_a_check_that_really_exits_124_or_127_is_a_failure_with_that_exit_code`
  (the timeout runs the real check with a short limit, since the entry point
  cannot configure it).
- Verdict depends only on the exit code:
  `test_failure_words_in_the_output_of_a_passing_check_do_not_change_the_verdict`,
  `test_ok_in_the_output_of_a_failing_check_does_not_change_the_verdict`.
- Prompts carry the log and the evidence rules:
  `TestStoryFromStartToPublication.test_every_agent_prompt_carries_the_evidence_rules_and_the_workflow_check_log`,
  `test_no_prompt_or_brief_tells_an_agent_to_read_or_paste_test_output_in_the_item`,
  `TestRunRecord.test_the_tester_after_a_failure_is_pointed_at_the_log_that_failed`.
- `dev-team check` prints a checkout-relative path: `TestCheckCommand` (both tests).
- Copy to `docs/work-items`: `TestPublicationCopy` (unchanged copy, masked copy).
- Match rule and masking table, no-trip list, idempotence, this item's own
  body: `TestCopyGuardRule` (all five tests).
- Backlog commits: `TestBacklogCommits` covers success, non-zero exit, a
  different item, a concurrent capture by a second process, a non-Markdown file
  and a root file, broken front matter, front matter left alone, `capture
  --file`, no unmasked file when nothing trips, committed lines left alone, and
  `rejected` feedback. `TestTerminalNotification` covers the TUI note.
- Test run text free of machine paths: `assert_no_machine_path` in the
  `TestRunRecord` tests and `TestStoryFromStartToPublication`.
- No log tracked on any branch after a full story:
  `test_the_record_copied_for_publication_matches_the_item_and_no_log_is_tracked_in_the_product`.
- Completed records unchanged: `TestRecordsAlreadyCompleted`.
- The home-directory reading test in `tests/test_launcher.py` is unchanged and
  passes with the suite. The `[human]` criterion is not automated.

## Test run

Run by the harness, 2026-10-08 18:35 UTC. Full output: `backlog/log/STORY-014/verify-20261008T183238224663.log`

Passed: `the project check`

```text
uv run python -m unittest discover -s tests
.......................................................................................................................................................................................................................................Executing <Task pending name="message pump Screen(id='_default')" coro=<MessagePump._process_messages() running at .venv/lib/python3.13/site-packages/textual/message_pump.py:571> wait_for=<Future pending cb=[Task.task_wakeup()] created at <path>:459> created at <path>:410> took 0.119 seconds
..Executing <Task pending name='screen_update' coro=<Timer._run_timer() running at .venv/lib/python3.13/site-packages/textual/timer.py:146> wait_for=<Future pending cb=[Task.task_wakeup()] created at <path>:459> created at <path>:410> took 0.116 seconds
..Executing <Task pending name='message pump Actions()' coro=<MessagePump._process_messages() running at .venv/lib/python3.13/site-packages/textual/message_pump.py:571> wait_for=<Future pending cb=[Task.task_wakeup()] created at <path>:459> created at <path>:410> took 0.152 seconds
....Executing <Task pending name='screen_update' coro=<Timer._run_timer() running at .venv/lib/python3.13/site-packages/textual/timer.py:146> wait_for=<Future pending cb=[Task.task_wakeup()] created at <path>:459> created at <path>:410> took 0.143 seconds
Executing <Task pending name="message pump Screen(id='_default')" coro=<MessagePump._process_messages() running at .venv/lib/python3.13/site-packages/textual/message_pump.py:571> wait_for=<Future pending cb=[Task.task_wakeup()] created at <path>:459> created at <path>:410> took 0.205 seconds
...Executing <Task pending name="message pump Screen(id='_default')" coro=<MessagePump._process_messages() running at .venv/lib/python3.13/site-packages/textual/message_pump.py:571> wait_for=<Future pending cb=[Task.task_wakeup()] created at <path>:459> created at <path>:410> took 0.171 seconds
......Executing <Task pending name='screen_update' coro=<Timer._run_timer() running at .venv/lib/python3.13/site-packages/textual/timer.py:146> wait_for=<Future pending cb=[Task.task_wakeup()] created at <path>:459> created at <path>:410> took 0.178 seconds
....Executing <Task pending name='message pump Answers()' coro=<MessagePump._process_messages() running at .venv/lib/python3.13/site-packages/textual/message_pump.py:571> wait_for=<Future pending cb=[Task.task_wakeup()] created at <path>:459> created at <path>:410> took 0.218 seconds
.......................
----------------------------------------------------------------------
Ran 275 tests in 144.269s

OK
```

## Review

Re-ran the whole suite on this branch: 275 tests, OK. The earlier review's five findings are addressed in the diff (fixture-based body tests, ASCII quotes in prompts/test.md, changed-files-only commit scan, relative notice paths, file line numbers in the copy notice).

Findings, most damaging first. None blocks approval.

1. **The live item body still trips its own guard until the next verify.** Trigger: run `PathGuard(checkout).mask` over `backlog/stories/STORY-014.md` as it stands. The `## Test run` section is in the old format (`Full output:` with the absolute log path, plus a fenced block of check output carrying home-directory paths), so lines of it are masked. The criterion says the guard over the whole body trips nothing, and the Implementation notes say the legacy section was replaced; the file shows it was not. The tests do not catch this because they use `tests/fixtures/evidence/STORY-014-criteria.md`, which covers the criteria text only. Effect today: the publish copy would be masked and a notice reported, so nothing leaks, but the criterion as worded is unproven for the real body. Fix: the harness's next verify rewrites the section in the new outcome-only format; confirm the guard then leaves the whole body untouched. If the fixture drifts from the item's criteria the test will not notice, so consider asserting the fixture text appears in the item.

2. **Minor: the TUI's notice sink is `App.notify`, which may be called from a worker thread.** `Repository.commit` runs the guard under the write lock, and the TUI repository may be used off the UI thread. Textual's `notify` is not documented as thread-safe. No failing input shown; `call_from_thread` would be safer if any commit path runs off the UI thread.

Criteria found satisfied, with evidence:

- Passing and failing test-run records with exit code, UTC time, duration, and no output, absolute path, fence or log path: `Runner.verify` in devteam/runner.py; `TestRunRecord` starts the harness as a process and asserts no machine path.
- Timeout and cannot-be-started shown without an exit code; real 124/127 recorded as failed with that code; log still written: `check.Result.status` is set in the `TimeoutExpired` and `OSError` branches, and `verify` shows the code only when `status == "finished"`; three dedicated tests.
- Verdict depends only on the exit code: nothing parses output; the OK/FAILED/Traceback tests.
- `{{verify_log}}`, `{{evidence_dir}}`, the `PROTOCOL` "Run evidence" section, and the edits to `implement.md`, `review.md`, `test.md`, `roles/implementer.md`; the `defect` wording requires the failing log's relative path: in the diff, with prompt-rendering tests.
- `dev-team check` prints a checkout-relative path (`cmd_check`, `TestCheckCommand`).
- Copy-guard match rule, masking, idempotence, front-matter exclusion, saved `unmasked-` and `log/unmasked/` copies, guard on every CLI `Repository`, notice sinks (print, runner `report`, TUI `notify`): devteam/evidence.py, devteam/cli.py, devteam/tui.py, devteam/runner.py; `TestCopyGuardRule`, `TestBacklogCommits`, `TestTerminalNotification`, `CommitMasking`.
- Test run text free of machine paths; guard values come only from `self.checkout`, `config.ROOT` and `sys` (the launcher home-directory test passes in the full run).
- Publisher prompt warning (prompts/publish.md); no `log/` file tracked in the product; completed records unchanged (`TestRecordsAlreadyCompleted`).
- The `[human]` end-to-end criterion is not automated and is left for the customer.
