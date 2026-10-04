# Platform-engineer analysis and backlog handoff

Purpose: platform analysis input for the PO's canonical backlog.
Read: `workspace/brief.md`, `team/README.md`, `team/platform-engineer.md`,
`.claude/skills/platform-engineer/SKILL.md`, `README.md`, `config/workspace`,
`config/roles.toml`, and `devteam/{engines,config,workitem,pipeline,cli}.py`.
The configured engagement resolves to this repository's `workspace/`.
Only `workspace/platform.md` and this file are owned by this role. Assumptions and
candidate requirements are kept here rather than editing shared assumption/backlog
files; the PO owns all canonical EPIC/STORY records and their authorisation.

## Evidence and consequences

| Observed prototype behavior | Operational consequence |
| --- | --- |
| `engines.run` calls blocking `subprocess.run`, with no timeout or process-group lifecycle handling | Cancellation, hanging agents and restart reconciliation need explicit design |
| Invocation header records full argv; stdout/stderr share a transcript | Prompts and briefs are persisted; nonsecret evidence cannot be assumed |
| `build_argv` supplies the item directory as `extra_dir`; config maps a single read/write access flag to engine permissions | Metadata authority and target-code access are not independently enforced |
| `pipeline.STAGES` grants intake write access and creates a worktree for investigation | Existing flags/layout do not establish safe analysis-only operation |
| `workitem.py` loads/saves `state.json` and stage responses are sibling JSON files | Incompatible with confirmed front-matter authority; do not feed these proposals to the runner |
| `step` saves running state before invocation, then consumes permissively parsed decisions | No durable attempt reconciliation, revision protection or validated named-outcome contract is established |
| `ensure_worktree` trusts an existing path; cleanup uses forced removal and recursive deletion | Existing path is not evidence of correct repo/branch; cleanup can destroy unpublished changes |
| `config.py` resolves resources from the source tree; README requires Python 3.11+ and installed agent CLIs | Packaging and offline test operation need an explicit contract |
| `roles.toml` contains product_owner, analyst, implementer and reviewer, not the five discovery charters | Runtime role mapping must be validated; discovery role availability must not be inferred |
| No `tests/`, `.github/` or packaging manifest was found in the inspected tree | No existing test/CI/package contract was evidenced; not proof none exists elsewhere |

`git status` could not identify this mounted workspace as a Git repository. No
branch, remote or GitHub configuration was established. No attempt was made to
repair Git, invoke the pipeline, call providers or inspect credentials. README's
claim that stages resume from disk is not evidence of safe crash recovery.

## Candidate requirements for PO mapping

The PO owns canonical EPIC/STORY files and should map these requirements into
those files, consolidating overlaps. This table is analysis input, not a separate
backlog: it defines no work-item IDs, states, dependencies or authorisation fields.
Canonical front matter, including `authorisation: not-played`, remains the sole
work-item authority. No new actual epics or stories are created here.

| Area | Candidate requirement | Suggested verification for canonical stories |
| --- | --- | --- |
| Bootstrap | Reproducible local installation with explicit Python/dependency support and installed resources; stable harness separate from candidate checkout/environment; fixture workspace and fake engines need no provider credentials. | Install outside the source tree; capture → analysis → human answer → repeated analysis → ready without play; another eligible item progresses during a human wait; live engagement remains untouched. |
| Lifecycle/recovery | Persist attempt identity and expected revision in front matter before dispatch; validate named outcomes; supervise cancellation/timeouts; commit atomically with conflict checks; reconcile interrupted attempts before explicit retry. | Exercise launch failure, nonzero exit, invalid response, timeout, cancellation, crash around dispatch/commit, duplicate/stale results and concurrent edits; preserve questions and approvals; reap owned processes without relying on stale PIDs. |
| Permission boundary | Separate scheduler metadata authority, agent result submission and target-code access; enforce scoped paths and engine capabilities; consultations cannot broaden permissions; worktrees are not security sandboxes. | Deny analysis writes to code and authoritative metadata while allowing results; reject traversal/symlink escapes and unsupported isolation; validate worktree identity and preserve dirty changes before later cleanup. |
| Evidence | Show item/attempt, owner, questions, failure and recovery action from front matter; retain minimal nonsecret linked evidence with restricted paths/permissions; document compatible-build and document recovery. | Secret-shaped fixture values stay out of logs/exports; missing evidence does not change history; restore compatible runtime/documents and reconcile before dispatch; readiness and passing checks never grant play or release. |

Technical detail remains in `../platform.md`. Repository/branch storage locations,
timeout values, retention and supported platform choices remain open.

## Later scope and coordination

PO mapping should retain later GitHub/CI, implementation/delivery, staging/release
and sprint-zero/specialist-extension scope in canonical epics. No later stories
are decomposed here. GitHub integration requires confirmed repository identity,
permissions and mapping; CI should reuse offline checks and nonsecret evidence.
Hosted infrastructure is unnecessary for the proposed local first slice.
Target-product hosting, deployment and rollback constraints are discovered per
product, separately from harness runtime requirements.

Architect input is needed for schema/versioning, atomic writes, response envelopes
and workflow validation; PO input for human answers, play and TUI journeys; quality
lead input for fault and permission fixtures. These are coordination needs, not
workflow collaborator fields. Delivery manager routes unresolved decisions and
customer prioritisation; canonical items alone record authorisation.

## Assumptions, separately recorded

| ID | Platform proposal, not customer decision | What changes it |
| --- | --- | --- |
| PA1 | Local foreground runtime and one active workspace writer suffice initially | Confirmed remote/multi-user operation or parallel scheduling need |
| PA2 | Stable runtime plus isolated candidate checkout/environment is the bootstrap approach | Customer's preferred installation/release workflow |
| PA3 | Offline fake-engine verification is the default; real-engine checks are opt-in | An agreed credentialed compatibility testing policy |
| PA4 | First-slice operation needs no hosted infrastructure | Customer requires shared access or continuous unattended hosting |
| PA5 | Minimal restricted evidence, with no raw transcript by default, is sufficient | Demonstrated debugging/audit needs plus an agreed data policy |

## Owned questions for the next decision round

- PQ1 — Platform engineer, with architect: where should work items, target repos
  and worktrees be stored, and which repository/branch versions item documents?
  This remains open; the prototype's `workspace/work` layout is not a decision.
- PQ2 — Platform engineer: which local OS/environment and installation workflow
  must the first slice support? Proposal: validate the customer's actual local
  environment first, and agree a wider support matrix before claiming portability.
- PQ3 — Platform engineer, with quality lead: what invocation timeout/cancellation
  policy and recovery evidence retention are acceptable? No values are assumed.
- PQ4 — Platform engineer: do initial agents require network access or credentials
  beyond their provider login, and what sensitive product data may enter evidence?
- PQ5 — Platform engineer, routed later: which GitHub repository/integration actions,
  CI runner model and budget are intended? Local analysis does not depend on this.

Next handoff: delivery manager/product owner consolidate and prioritise the proposed
work; architect resolves storage and permission contracts with platform input.
No availability target, cost ceiling or usage metric was supplied, so no numeric
estimate or budget/availability conflict can responsibly be asserted.
