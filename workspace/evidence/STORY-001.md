# STORY-001 implementation evidence

Date: 2026-10-02. The customer explicitly instructed
`play story ./workspace/stories/STORY-001.md`. Implementation used the controlled
session bridge in plan.md; it did not invoke the legacy ITEM pipeline.
Authoritative item status and session provenance are in the story's front matter.

## Acceptance results

| Criterion | Evidence | Result |
| --- | --- | --- |
| All supported types round-trip identity, links and narrative; front matter alone supplies state | `test_four_types_roundtrip_and_front_matter_authority`: epic/story/task/bug, Unicode, CRLF/whitespace, dependencies, nested extension values, contradictory body and JSON | Pass |
| Duplicate IDs, missing parents/dependencies, cycles, malformed front matter and unsupported versions fail per file without repair | Duplicate collision, missing references, dependency/parent cycle tests; 15-case negative YAML matrix; dependent quarantine and independent valid records; invalid capture leaves bytes unchanged | Pass |
| Newly captured work remains unplayed with zero agent calls/tokens on idle scans | `test_capture_idle_restart_zero_calls_or_tokens`: recording fake engine, three scans with fresh repositories, adversarial narrative, played/implemented extension attempt; legacy step patched to fail if invoked | Pass: 0 calls, 0 fake provider tokens |

Additional checks cover CLI capture/validate/scan and nonzero failure status,
symlink escape rejection, ID allocation, and compatibility with this workspace's
six epics and ten stories. No provider credentials or live agents are used.

Reproduce with:

```sh
python3 -m unittest discover -s tests -v
python3 -m devteam backlog --workspace workspace validate
python3 -m devteam backlog --workspace workspace scan
```

The final run passed 11 tests. Captured output is in
[STORY-001-tests.txt](STORY-001-tests.txt); the planning validation output is in
[STORY-001-validation.txt](STORY-001-validation.txt).

## Reconciliation and limits

- Implements STORY-001's subset of quality checks V0/V1: planning records,
  validation and zero dispatch before Analyse. It does not claim the later
  runtime transitions, typed questions/history or replay checks are implemented.
- Adopts pinned PyYAML 6.0.3 with a strict safe loader. Parent policy, supported
  planning fields, extension preservation and unsupported YAML constructs are
  specified in [schema documentation](../../docs/backlog-schema-v1.md).
- `implemented`/`played` describe this controlled session. They are not a runtime
  completion proof, release gate or a schedulable workflow binding. The scheduler
  deliberately returns no eligible planning items, even for these values.
- Capture creates new files only. STORY-002 owns atomic updates, coordinated
  allocation, concurrency, revision/content checks and crash recovery. No such
  guarantees are claimed by this slice.
- Runtime analysis/enrollment remains in STORY-004/005; no legacy fallback,
  engine invocation or sibling authoritative JSON store was added.
- Integration validation initially exposed an incorrect plural directory for
  stories that the temporary fixtures shared. Explicit directory mapping and a
  regression check against the existing backlog now cover it.
- Git metadata is unavailable in this mounted workspace, so no commit, branch,
  PR or independent diff-based review was produced. No deployment or release
  was performed.
