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
