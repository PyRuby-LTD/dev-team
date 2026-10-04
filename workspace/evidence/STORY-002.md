# STORY-002 implementation evidence

Date: 2026-10-04. The customer explicitly instructed
`play story ./workspace/stories/STORY-002.md`. This used the controlled-session
bridge in plan.md, following the implemented STORY-001 dependency. No legacy
pipeline or external agent/provider was invoked. Item status and provenance are
authoritative in STORY-002 front matter.

| Acceptance criterion | Reproducible evidence in tests/test_storage.py | Result |
| --- | --- | --- |
| Interrupted replacement yields complete old or new Markdown | `test_write_fault_matrix_old_or_complete_new`, `test_process_crash_matrix_and_lock_recovery`, `test_actual_replace_and_fsync_errors_preserve_atomic_document`: nine checkpoints each for exceptions and hard process exit; real syscall failures; complete new history after publication | Pass |
| Two same-source managed writers yield one commit and one conflict | `test_competing_process_updates_one_success_one_conflict`: barrier synchronizes two separate processes after loading the same revision/digest; exactly one event/revision/body survives | Pass |
| Paused manual metadata/body edit imports with new revision and invalidates old responses; malformed edit remains blocked | `test_pause_manual_import_restart_and_stale_response_invalidation`, `test_malformed_manual_edit_remains_visible_and_untouched`, `test_resume_protects_history_and_rejects_stale_digest`: restart, unchanged revision, Unicode/CRLF, extension preservation, dispatch invalidation, obsolete tokens, malformed bytes preserved | Pass |
| Unsupported edits produce explained conflicts | `test_unpaused_body_and_metadata_edits_conflict_without_overwrite`, `test_final_digest_check_detects_edit_during_temp_write`: body/metadata/malformed and same-size edits; final comparison detects save during preparation; exact edited bytes survive | Pass |
| Restart reconstructs execution failure and evidence from Markdown, independently of workflow progress | `test_persisted_failure_and_evidence_do_not_advance_workflow`: fresh repository ignores contradictory state.json, preserves failure/evidence/history, state remains proposed, no scheduling | Pass |
| Invalid update preserves valid content and unrelated fields | `test_rejected_updates_preserve_all_bytes`: malformed/protected metadata, invalid parent/cycle/execution evidence; full before/after byte equality including nested extension data | Pass |

Additional checks cover coordinated capture allocation, revision-zero compatibility,
malformed storage diagnostics, CLI pause/resume/update and stale rejection. Existing
STORY-001 tests continue to prove capture/scans never dispatch agents.

Reproduce:

```sh
python3 -m unittest discover -s tests -v
python3 -m devteam backlog --workspace workspace validate
python3 -m devteam backlog --workspace workspace scan
```

The final suite passes 26 tests (11 existing and 15 storage checks). Captured output:
[tests](STORY-002-tests.txt), [validation](STORY-002-validation.txt).

Storage decisions are in [ADR-002](../decisions/ADR-002.md); the additive schema,
commands and supported manual-edit protocol are in
[schema documentation](../../docs/backlog-schema-v1.md). This implements the storage
subset of quality checks V1/V5/V6/V7. It supplies correlation invalidation rather
than a runtime response consumer. Workflow enrollment, named outcomes, questions,
attempt reconciliation, response deduplication and dispatch remain later-story work.

Verification ran on the mounted local Linux filesystem. Process-crash and syscall
failure evidence does not prove hardware power-loss durability or network filesystem
behavior. A noncooperating editor can still save between final comparison and rename;
the supported pause/edit/resume protocol excludes that race. An error after publication
requires reopening before retrying. No multi-item transaction or external exactly-once
claim is made. No deployment, release or live-provider run occurred. The mounted
`.git` directory is empty; no commit, PR or independent diff review was available.
