---
id: STORY-019
type: story
title: Serialise backlog writes across processes and commit by path
parent: EPIC-007
workflow: default
step: publish
---
**As a** customer running several dev-team agents at once
**I want** every `dev-team` process to serialise its backlog writes and commit only the files it changed
**So that** concurrent agents never fail on git's index lock or commit another item's half-edited file under the wrong message

## Context

`WRITE` is an in-process RLock only. Agents call `dev-team` as subprocesses, each with its own `Repository` and lock, so with several agents running a `git commit` can hit `index.lock`, raise `GitError`, and fail the step. `commit` also runs `git add -A` over the whole backlog, sweeping in other items' edits. Linux and macOS only (`fcntl.flock`). The lock file lives under the backlog's ignored `log/` directory.

## Analysis

Findings against the repository:

- `devteam/backlog.py` `WRITE` is a `threading.RLock`; it serialises threads in one process only. The CLI, the runner and the agents' `dev-team` subprocesses each build their own `Repository`, so nothing serialises across processes. The premise holds.
- `Repository.commit(message)` takes no paths. It runs the guard and then `git.commit_all(root, message)`, which does `git add -A -- .` and a path-less `git commit`. Any other item's uncommitted edit is swept in under the wrong message.
- `create`, `transition` (via `_transition`) and `write_body` all end in `self.commit(...)` with no paths. `transition` with a note makes two commits: feedback through `write_body`, then the step change.
- `devteam/evidence.py` `PathGuard.__call__` scans every changed or untracked file in the whole backlog and rewrites any containing machine paths. A path-scoped commit therefore also needs a path-scoped guard. Otherwise the guard rewrites item B's half-edited file on disk while committing item A.
- `git.commit_all(directory, message, *paths)` already supports paths, and `git commit -- <paths>` leaves other staged files out.
- `devteam/runner.py` (~line 344) calls `self.repository.commit(f"{id}: {step} failed")` with no paths: a third whole-backlog commit site.
- `tests/test_evidence.py` `CommitMasking` calls `repo.commit("changed")` with no paths and expects the whole-tree guard and commit, so the no-path form must keep working or that test must be changed deliberately.
- `_replace` writes `<item>.md.tmp` then renames it; a concurrent whole-tree `add -A` could sweep up the temporary file.
- `git.ensure_backlog` writes `log/` into the backlog `.gitignore` when it creates the orphan branch, so a lock under `log/` is untracked for backlogs created that way.
- Linux and macOS only (`fcntl.flock`) is accepted in the item.

Decisions I am comfortable stating (not questions):

- The lock is an exclusive, blocking `fcntl.flock` on a file under the backlog's `log/` directory (created if missing), held for the whole mutation: scan, validate, write and commit. That also makes ID allocation in `create` safe across processes.
- Lock ordering is fixed (OS lock, then `WRITE`) and re-entrant within a process, so `transition` calling `write_body` and `commit` does not block on itself.
- `commit` gains optional paths. When given, both the guard and `commit_all` are limited to them. With none, current behaviour is kept for whole-backlog callers and the existing test.

- Challenge findings 2 and 3 are accepted and applied to the criteria below: the runner failure commit is path-limited, and "no `git add -A`" means nothing outside the given paths is staged.
- Challenge finding 1 is confirmed: `prompts/analysis/product-owner.md:34-35` tells the product owner to edit other items' bodies on `revise`, and today the runner's `transition` on the request (`devteam/runner.py:283`) sweeps those edits in via the whole-backlog commit. Path-scoped commits would leave them uncommitted. Question 1 is answered: the customer accepts path-scoped commits with no runner sweep and no prompt change. Each step acts on one item, so only that item's file needs committing. The known gap is that an agent's direct edits to other items (for example epics revised by the product owner) stay uncommitted on disk until someone commits them; items created through `dev-team create` are still committed at creation. Giving those edits a way to be committed (the customer suggested an "uncommitted epic changes" state) is a separate feature and out of scope here; it should be raised as its own backlog item. This story must not commit those edits, and must not let any other item's commit sweep them in.

## Acceptance Criteria

- [ ] **Given** two separate OS processes each calling `transition` on a different item in a temporary git backlog, started together, **When** both finish, **Then** both succeed, and each new commit changes exactly that item's file and carries its own `ITEM: name -> target` message.
- [ ] **Given** `create`, `transition` and `write_body`, **When** each commits, **Then** the commit contains exactly the files that call wrote and nothing else, and nothing outside the given paths is staged or committed (`git add -A -- <paths>` limited to those paths is fine). A transition with a note produces a feedback commit and a step commit, both limited to that item's file.
- [ ] **Given** item B has an uncommitted in-place edit and an unrelated untracked file exists, **When** a commit is made for item A, **Then** neither is in A's commit, both are still uncommitted afterwards, and B's file on disk is unchanged, even if B's edit contains a machine path the guard would mask.
- [ ] **Given** a guard is configured, **When** a commit is made by path, **Then** only those paths are masked. A commit with no paths still masks and commits the whole backlog as `CommitMasking` in `tests/test_evidence.py` expects.
- [ ] **Given** one process holds the OS-level lock, **When** another process starts a mutation, **Then** it blocks until the first releases, then succeeds with no `GitError` or `index.lock` failure. If the holder is killed, the lock is released and a later mutation succeeds.
- [ ] **Given** threads in one process, **When** they mutate concurrently, **Then** they are still serialised by `WRITE`, and nested calls (`transition` calling `write_body`) do not deadlock.
- [ ] **Given** a backlog created by `git.ensure_backlog`, **When** a mutation has taken the lock, **Then** the lock file exists under `log/` and appears in neither `git status --porcelain` nor `git ls-files`.
- [ ] **Given** a runner step fails, **When** the failure is recorded, **Then** that commit (`devteam/runner.py:344`) contains only the failing item's file, and other items' uncommitted edits (including a revised epic or story edited on disk) stay uncommitted and unmasked.
- [ ] **Given** a runner `transition` on a request after the product owner edited EPIC-X on disk during a revise, **When** the request's transition commits, **Then** the commit contains only the request file and EPIC-X remains modified and uncommitted (accepted behaviour, Question 1).
- [ ] `dev-team check` passes.

## Challenge

Sound. A competent engineer could build this as written, and a reviewer could tell whether they had. All three earlier findings are resolved. The customer's answer to Question 1 is recorded faithfully as an accepted gap, scoped out, and turned into AC 9. AC 8 now names one build. AC 2 now says "nothing outside the given paths is staged", which matches `git add -A -- <paths>` in `devteam/git.py:73`.

I re-checked the claims against the repository and they hold:

- **Commit sites.** After this story, the only backlog commit sites are `create` (`devteam/backlog.py:254`), `write_body` (`:280`), `_transition` (`:310`) and the runner failure commit (`devteam/runner.py:344`). The criteria cover all four. The runner's other `commit_all` calls (`devteam/runner.py:257`, `:282`) are on the product checkout, not the backlog, so they are rightly left alone.
- **New stories.** The product owner passes bodies at creation through `capture --file` (`devteam/cli.py:33-34`), so new stories are committed in full at creation. The analysis says so, and it is correct. A story the product owner revises on disk is picked up by that story's own next transition, which writes the same file. That matches the customer's answer that the real gap is epics.
- **Lock file location.** `log/` is ignored in this backlog (`backlog/.gitignore`), and `git.ensure_backlog` writes the same rule (`devteam/git.py:100`), so AC 7 can be checked.

One minor point, which does not block: the no-path, whole-backlog form of `commit` will have no production caller once the four sites take paths. AC 4 keeps it only for `CommitMasking`. If it stays, it is the one remaining way for EPIC-X's edits to be swept in. The implementer should keep it out of production code paths. Alternatively, the analyst could later decide to retire it along with the test.

## Questions

1. When an agent edits items other than its own during a step (for example the product owner revising earlier stories and epics), how should those edits be committed once commits are path-scoped? Option A: the runner commits every backlog file that changed during the step, as part of that step's transition, under the step's message; no prompt change, but it could capture a concurrent agent's edits to the same files. Option B: the agent changes other items only through a `dev-team` command that commits by path, and the prompt is changed to say so; stricter, but relies on agents following the prompt.

   **Answer:** I don't really see this as an issue. Scenario A: I create a new request and kick off analysis, this updates the request and creates / updates epics and creates new stories. If the only thing that gets committed is the request, that's okay but not ideal, only because epics will never get committed that way. If I then move a created story on to be analysed, that analysis should only act on the one story, so that makes it simple that only the story being analysed should be worked on. So the gap is epics. Perhaps there needs to be a state for epics as uncommitted changes so I can choose to commit them.

## Implementation

Implemented process-wide backlog mutation serialisation and path-scoped commits. `create`, `transition`, `write_body` and `commit` take a blocking exclusive `fcntl.flock` on `log/backlog.lock` before `WRITE`, holding both across scan, validation, writing, masking and commit. Thread-local ownership makes nested calls re-entrant, including calls through another Repository for the same root. Kernel ownership releases the lock when its holder dies.

All four production backlog commit sites now pass only their item's path. PathGuard limits its changed, staged and untracked file discovery to the supplied paths, including an unborn branch. The no-path API retains whole-backlog masking and committing. Other items' direct edits remain on disk, uncommitted and unmasked, as accepted in the analysis. No prompt changes or sweep of other items were added.

Acceptance coverage (below end-to-end level, using real temporary Git repositories):

1. Covered by `tests.test_backlog_writes.BacklogWrites.test_two_processes_transition_with_separate_commits`: separate spawned OS processes start together; both succeed; the two commits have their own exact messages and item paths.
2. Covered by `test_create_body_and_noted_transition_commit_only_their_item`: creation, body writes and both commits of a noted transition contain only their item. An unrelated staged change stays staged and no additional outside path is staged.
3. Covered by the same test: another story, a revised epic and an unrelated untracked file retain their original bytes, including maskable machine paths, and remain uncommitted.
4. Covered by that test and `tests.test_evidence.ChangedFiles.test_path_scope_on_unborn_branch_leaves_other_files_unmasked`. Existing `CommitMasking.test_only_changed_lines_are_masked_with_originals_saved` still proves the no-path whole-backlog behaviour.
5. Covered by `test_mutation_waits_for_lock_release_or_holder_death`: a second process cannot mutate while the lock is held; it succeeds after normal release or SIGKILL of the holder.
6. Covered by `test_threads_use_write_and_nested_calls_do_not_deadlock`: a thread waits for `WRITE`, a noted transition completes its nested calls, and concurrent creates through separate Repository instances allocate distinct IDs and leave a valid backlog.
7. Covered by `test_lock_file_is_ignored_in_ensure_backlog_worktree`: a real worktree created by `ensure_backlog` contains the lock under `log/`, with clean status and no tracked lock file.
8. Covered by `tests.test_runner.RunnerAcceptance.test_failure_commit_leaves_other_items_uncommitted_and_unmasked`: a failing fake agent edits its own item; the real runner commits only that item and preserves unrelated story and epic edits.
9. Covered by `test_request_transition_leaves_revised_epic_uncommitted`: after a request enters revise, a fake product owner edits the epic and request on disk; the real runner's transition commits only the request and leaves the epic modified and unmasked.
10. No additional unit test: running `dev-team check` is the criterion itself; result recorded below. These tests prove the specified behaviour without a running system; the tester can add narrative confirmation independently.

Checks and evidence:

- Direct module tests: `.venv/bin/python -m unittest tests.test_backlog_writes tests.test_backlog tests.test_evidence tests.test_runner` passed, 40 tests. Final output: `backlog/log/STORY-019/unit-modules-final.log`.
- Initial test run had two test-authoring expectation errors (Git helper trimming leading status whitespace and the request workflow target); corrected and re-run successfully. Earlier output: `backlog/log/STORY-019/unit-writes.log`; the first successful module run is `backlog/log/STORY-019/unit-modules.log`.
- Initial `uv run` could not write its default cache in this sandbox; output: `backlog/log/STORY-019/unit-initial.log`. Subsequent uv commands use `UV_CACHE_DIR=/tmp/devteam-story-019-uv-cache`; direct unit tests use the existing virtual environment.
- `uv build --out-dir /tmp/devteam-story-019-dist` passed, producing a source distribution and wheel; output: `backlog/log/STORY-019/build.log`.
- `git diff --check` passed; output: `backlog/log/STORY-019/diff-check-final.log`.
- Initial `dev-team check` failed, 283 tests with three failures: `TestBacklogCommits.test_a_path_written_to_a_different_item_is_masked_in_the_commit`, `test_a_non_markdown_file_beside_the_item_and_a_file_in_the_backlog_root_are_masked`, and `test_an_item_captured_by_another_process_while_the_engine_runs_commits_nothing_tripping`. Saved harness output: `backlog/log/check/20261014T125214125428.log`. These expectations required whole-backlog masking during another item's capture/transition, directly contradicting AC 2–4. Updated the three superseded tests to expect untouched/uncommitted unrelated files, and masking of the active item during its own transition. No narrative suite was added.
- Re-ran the entire changed `tests.test_run_evidence` module directly; passed, 33 tests, including all three superseded failing scenarios. Output: `backlog/log/STORY-019/unit-run-evidence.log`.
- Final `dev-team check` passed, 283 tests. Saved harness output: `backlog/log/check/20261014T125521362870.log`.
- No separate linter or type-check configuration is provided by the project. No prior workflow check log, review findings, tester defects or PR feedback were supplied.

No implementation criteria are blocked. Changes are left in the working tree for the runner to commit.

## Tests

Narrative test: `tests.test_concurrent_cli.ConcurrentBacklogCommits.test_parallel_moves_commit_only_their_own_item_and_leave_neighbours_alone`. It starts two real `dev-team backlog move` processes together on different stories in a product repository with a real backlog branch, while an epic and an unrelated file hold uncommitted edits containing machine paths. It checks both processes succeed, each new commit holds exactly its own item's file with its own message, the epic and stray file are byte-identical and still uncommitted, and the lock file exists under `log/` and is untracked (criteria 1, 2, 3, 7 and the request/epic gap of 9 in outline).

Left to the implementer's unit tests: the explicit lock hold and holder-kill behaviour (5), thread and nested-call serialisation (6), guard scoping and the no-path `CommitMasking` form (4), the runner failure commit (8) and the request transition leaving a revised epic uncommitted (9), and the create/body/noted-transition commit contents (2).

Run one test on its own: `dev-team check tests.test_concurrent_cli`.

## Test run

Run by the harness, 2026-10-14 13:12:55 UTC: passed (exit 0); duration 140.879 seconds.

## Review

No blocking findings. The change is sound.

Minor, not blocking:

- `mutation` in `devteam/backlog.py` keys re-entrancy on `(pid, root)` using the root path as given. A nested call through a Repository built with a differently spelled path to the same directory (relative, symlinked) would take a second `flock` on a new file description and block on itself. No production caller does this; resolving the root in the key would close it.
- The no-path form of `commit` remains, as the Challenge noted. No production site uses it now; only `CommitMasking` does.

Criteria satisfied:

1. Two processes, separate commits: `devteam/backlog.py` `mutation` takes `flock` on `log/backlog.lock` and each `_transition` commits `record.path` only. Proven by `tests.test_backlog_writes.BacklogWrites.test_two_processes_transition_with_separate_commits` and the tester's `tests.test_concurrent_cli`.
2. Create, transition and write_body commit only their file: all three pass `record.path` to `commit`, which passes it to `git add -A -- <paths>` and `git commit -- <paths>`. A noted transition makes two commits, both path-limited. Proven by `test_create_body_and_noted_transition_commit_only_their_item`.
3. Other item B and untracked files untouched: `PathGuard.__call__` limits `diff`, `ls-files --cached` and `ls-files --others` to the given paths, so B is neither masked nor committed. Proven by the same test and `tests.test_concurrent_cli`.
4. Guard by path, no-path still whole-backlog: `PathGuard` and `commit_all` fall back to the whole tree with no paths. Proven by `tests.test_evidence.ChangedFiles.test_path_scope_on_unborn_branch_leaves_other_files_unmasked` and the unchanged `CommitMasking` test.
5. Cross-process blocking and holder death: blocking `LOCK_EX` on a kernel lock, released on process death. Proven by `test_mutation_waits_for_lock_release_or_holder_death`.
6. Threads and nesting: the OS lock is taken before `WRITE`, and thread-local ownership lets nested calls skip the OS lock. Other threads in the process have no ownership, so they block on `flock`. Proven by `test_threads_use_write_and_nested_calls_do_not_deadlock`.
7. Lock file ignored: it sits under `log/`, which `ensure_backlog` writes to `.gitignore`. Proven by `test_lock_file_is_ignored_in_ensure_backlog_worktree` and the narrative test.
8. Runner failure commit: `devteam/runner.py:344` passes `record.path`. Proven by `tests.test_runner.RunnerAcceptance.test_failure_commit_leaves_other_items_uncommitted_and_unmasked`.
9. Request transition leaves the revised epic uncommitted: proven by `test_request_transition_leaves_revised_epic_uncommitted`.
10. `dev-team check`: the harness run in `backlog/log/STORY-019/verify-20261014T131034560348.log` passed (284 tests, OK).

Three tests in `tests/test_run_evidence.py` were rewritten because they asserted whole-backlog masking during another item's transition. That contradicts AC 2 to 4, so I accept the change as deliberate.
