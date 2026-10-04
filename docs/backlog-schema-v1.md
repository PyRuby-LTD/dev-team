# Markdown planning schema, version 1

STORY-001 implements the planning contract; STORY-002 adds the compatible
optional persistence fields described below. Records live beneath an explicitly
selected root in `epics/`, `stories/`, `tasks/` or `bugs/`, including nested
folders. Other Markdown files are narrative resources, not items. Each item file
starts with `---`, a YAML mapping and a closing `---` line. UTF-8 is required.
Type must match its directory. Paths escaping the root through symlinks fail.

| Field | Contract |
| --- | --- |
| `schema_version` | Required integer `1`; booleans and other versions fail |
| `id` | Required globally unique ID within the root, uppercase type prefix followed by an alphanumeric identifier with optional underscores/hyphens; e.g. `STORY-001` |
| `type` | Required `epic`, `story`, `task` or `bug` |
| `title` | Required nonempty string |
| `state` | Required `proposed`, `in-progress` or `implemented`; descriptive planning/delivery tracking only |
| `authorisation` | Required `not-played` or `played`; an external controlled session may record explicit customer play here |
| `depends_on` | Required list of unique IDs of direct prerequisites within the same root; empty allowed |
| `parent` | Epic: absent/null. Story: epic ID required. Task: story or bug ID required. Bug: absent/null or epic/story/task ID |
| `owner` | Optional nonempty planning attribution; never runtime step ownership |
| `detail` | Optional epic-only `detailed` or `deferred` |
| `x-*` | Optional YAML metadata preserved semantically; no scheduler authority |

The parent choices are this slice's proposed hierarchy policy. Parent and
dependency cycles, self-links, missing references and ambiguous IDs fail.
Dependencies can reference any supported type; hierarchy grants no inherited
permission or completion. IDs come from front matter, not filenames. Automatic
capture selects the first unused positive numeric ID for the type. Explicit
IDs must also be unique. Renames do not change identity.

Duplicate keys (including nested keys), non-string mapping keys, YAML aliases,
anchors, merge keys, custom tags, unknown fields, malformed delimiters and invalid
field types fail without repair. All colliding ID files receive diagnostics.
Records referencing invalid ancestors/prerequisites are also quarantined;
unrelated valid records remain available for inspection. Invalid UTF-8 and file
read errors are per-file diagnostics. CLI validation exits 1 when errors exist.

Capture always creates `state: proposed`, `authorisation: not-played`. It accepts
no permission override. Existing corrupt backlogs must be repaired before capture
to avoid allocating an ID that could already exist in an unreadable record.
Capture never overwrites an existing destination. Allocation, link validation,
capture and updates now share an advisory workspace mutation lock.

`Record.render()` preserves metadata values and exact narrative text, including
line endings and whitespace in the body. YAML comments, quoting and formatting
may be normalised. Scanning never writes. No JSON file or body assertion supplies
state. The loader never imports the legacy runner or an engine configuration.

The scheduler currently only scans and returns diagnostics/blocking reasons.
Every planning record is ineligible, even if manually marked played, or if its
body/extensions request dispatch. There is no Analyse command or engine execution
yet. Runtime enrollment, validated workflow ownership and explicit Analyse are
later-story requirements. `implemented` is not verified runtime completion and
cannot satisfy a future delivery prerequisite by itself.

This is deliberately not the eventual runtime contract. Questions/answers,
decisions, attempts and pinned workflows require extensions in dependent stories.
Only the storage fields below are available now. `x-session` retains session provenance
now; it is neither a runtime decision envelope nor permission to dispatch.

# Offline usage

Python 3.11+ and the pinned dependency in `requirements.txt` are required:

```sh
python3 -m pip install -r requirements.txt
python3 -m devteam backlog --workspace /tmp/example-backlog capture epic 'Example'
python3 -m devteam backlog --workspace /tmp/example-backlog capture story 'Feature' --parent EPIC-001
python3 -m devteam backlog --workspace /tmp/example-backlog validate
python3 -m devteam backlog --workspace /tmp/example-backlog scan
python3 -m unittest discover -s tests -v
```

Use `--file` for a narrative file, `--id` to choose an ID, and repeat
`--depends-on` for dependencies. The existing `new/run/step/status/show/decide`
commands still operate legacy ITEM directories. They do not accept Markdown
backlog IDs. Do not use them as a fallback to dispatch these records.

## Persistence fields and managed updates

| Field | Contract |
| --- | --- |
| `revision` | Optional nonnegative integer. Existing records without it load as revision zero; capture starts at one. Every accepted managed mutation increments it once. |
| `execution` | Optional mapping with required `status`: idle/pending/running/waiting-human/failed/uncertain. Optional nonempty `error`, list of nonempty `evidence` references, and `dispatch` correlation metadata. Does not change `state`. |
| `execution.dispatch` | Mapping containing exactly nonempty `id`, nonnegative integer `expected_revision`, and lowercase SHA-256 `expected_file_digest`. Storage correlation only; does not authorise dispatch. Workflow/attempt/response contracts remain deferred. |
| `history` | Optional list, created empty at capture. Managed writes append one unique event with actor, UTC timestamp, event name, before/after revision and state, original file digest and evidence references. A manual import may include `invalidated_dispatch`. Existing entries cannot be patched through the update API. |
| `manual_edit` | Present only while paused: paused_revision, baseline_digest and protected_digest. Durable pause and import bookkeeping; never edit these fields manually. |

`Repository.update(loaded_record, changes=..., body=..., actor=..., evidence=...)`
uses the source revision and SHA-256 digest retained by the loader, independently
of mutable metadata. It reloads under `.backlog.lock`, checks the complete source
bytes and revision, validates the entire candidate and backlog links, then commits
body, metadata and appended history together. Identity/type/schema, revision,
history and pause fields are protected. Omitted fields and extensions survive;
YAML presentation is normalised, and unchanged narrative bytes survive.
Backlog validation errors block mutations until repaired. Scan remains read-only.

The optional `fault` hook exists for deterministic storage tests, not agent input.
No file digest is stored as its own field inside the file it hashes. Commands
require the revision and complete-file digest printed by `scan`:

```sh
python3 -m devteam backlog --workspace /tmp/example-backlog scan
python3 -m devteam backlog --workspace /tmp/example-backlog update STORY-001 --revision 1 --digest <digest-from-scan> --title 'Revised title'
python3 -m devteam backlog --workspace /tmp/example-backlog pause STORY-001 --revision 2 --digest <latest-digest>
# Edit the paused document, validate, and scan again to obtain its changed digest.
python3 -m devteam backlog --workspace /tmp/example-backlog validate
python3 -m devteam backlog --workspace /tmp/example-backlog scan
python3 -m devteam backlog --workspace /tmp/example-backlog resume STORY-001 --revision 3 --digest <edited-file-digest>
```

Update also accepts `--file` for a replacement body, repeatable `--evidence`, and
`--actor` for the trusted local operator's audit label. The label is not remote
authentication or a workflow permission check. The CLI grants no analysis intent.

## Supported manual editing and reconciliation

Pause first, before opening/saving an editor. The pause commit records its
revision and baseline in the item; managed updates refuse paused items across
restarts. Edit narrative, title, links, owner/detail or extension metadata. Retain
identity, schema, revision, state/authorisation, execution, history and pause
bookkeeping. Progress and permission require managed actions. Resume rejects
changes to these protected fields. Digests are integrity checks for cooperating
operators, not tamper-proof signatures against filesystem owners.

Validate and scan the edited file; resume supplies that current digest and the
paused revision. Resume validates links, records a manual-import event if content
changed, increments revision, removes pause bookkeeping, and invalidates a pending
dispatch by removing it and recording its ID in history. Its pending/running/human
waiting status returns to idle; unrelated error/evidence fields are retained.
Old revision/digest response tokens fail future writes. An unchanged resume also
increments revision (ending the pause is a mutation); no response processing or
dispatch retry is implemented here. Malformed edits remain visibly blocked and
untouched; restore syntax and protected fields before attempting resume again.

Edits outside the protocol produce a conflict, including same-size body edits
without a revision bump. Reload and reconcile deliberately; never retry a stale
patch blindly. If an unsupported edit has already happened, retain its bytes,
reload and validate, pause the current valid record, then reconcile through the
supported protocol. Invalid files require operator repair first.

## Filesystem and acknowledgement boundary

Support is local Linux/POSIX filesystems implementing flock, same-directory
atomic rename/hard links, file fsync and directory fsync. The lock is coordination
metadata, contains no item state and must never be removed while writers run.
Every managed writer must use this repository. No multi-item transaction, network
filesystem guarantee or distributed coordinator is supplied.

Updates write a same-directory temporary file, flush and fsync it, check the
source again, replace atomically, then fsync the directory. Existing file mode
bits survive replacement; captures default to private mode 0600. Creation publishes
with a no-overwrite hard link. Normal failures clean temporary files; process death
may leave `.backlog-*.tmp` files, which scanners ignore and never use for recovery.
Reopening always reads the authoritative Markdown. Do not automatically promote
orphan files. Operators can remove them at a quiescent boundary.

A failure after replacement may mean the commit succeeded without acknowledgement.
Reopen and inspect revision/history before retrying. File/directory fsync provides
the intended durability boundary, but process-crash tests do not establish
power-loss durability across hardware or newly created directory hierarchies.

The final digest check detects edits during preparation. An editor ignoring pause
can still save between that check and replacement (or after replacement); rename
is not compare-and-swap against such an editor. Universal lost-update protection
is not promised. Pausing is the supported way to exclude this race.
