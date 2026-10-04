# Platform proposal: operating the delivery harness

Owner: platform engineer. Status: analysis proposal, not implementation approval.
Authority: `brief.md`; supporting evidence and proposed backlog records are in
`analysis/platform-engineer.md`. No agents or services were invoked for this analysis.

## Confirmed boundaries

The harness is this engagement's product. Python controls named, validated outcome
transitions; each workflow step owns one agent or human role, with no collaborator
field. Agents may choose to consult other roles. Markdown front matter alone owns
work-item state, including execution metadata and history. There is no database or
authoritative sibling state file. Analysis can repeatedly return to a human and
resume analysis. Readiness, customer play, and customer release are distinct.

The requested deliverable is analysis and proposed unplayed work. The first-slice
scope is a team proposal: capture, analysis, human answer, reanalysis, ready to play,
and minimal terminal visibility. Hosted infrastructure is not necessary for that
local slice. Target products may require cloud infrastructure, staging, deployment
pipelines, security and availability guarantees; those are discovered per product
and must not become assumed hosting requirements for the harness.

## Local runtime and bootstrap proposal

Use a foreground local Python process with explicit workspace selection, visible
startup validation and controlled shutdown. Keep human requests durable in item
front matter so a terminal exit does not discard them. A waiting item must not
hold the scheduler or prevent another eligible item being considered. Serial agent
execution is a proposed starting point, not a customer concurrency decision; a
bounded invocation must still be cancellable and cannot hang scheduling forever.

Maintain a stable installed/released harness for daily use while developing its
replacement in a separate checkout and environment. Tests use temporary fixture
workspaces and fake engine executables; never point a development smoke test at
the live engagement by default. Identify the harness build, workflow revision and
engine configuration used for each attempt. Do not hot-reload changed scheduler
code into a running process. Stop cleanly and select the new build explicitly.

The current documented entry point is `python3 -m devteam` with Python 3.11+.
Its `run` and `step` commands can reach implementation and are not suitable for
testing the proposed analysis-only flow on real items. Future bootstrap guidance
must provide a fixture-only smoke command and separate, explicit real-engine
checks. Missing credentials or CLIs should not prevent offline fixture testing.

## Process lifecycle and recovery requirements

Before dispatch, validate paths, selected role/engine, executable availability,
permission capability, workflow and item schema. Persist attempt identity and
expected item revision in front matter before launching. Capture launch failure,
nonzero exit, cancellation, timeout and invalid response as execution failures,
not successful workflow outcomes. Select timeout policy explicitly; no duration
is established here. Terminate and reap the owned process group on cancellation,
with bounded escalation and clear reporting if descendants cannot be confirmed
stopped. Do not kill processes based on an old PID alone.

The scheduler validates an outcome against the current step and attempt, then
commits state and history together with atomic same-filesystem replacement and
revision checks. Serialize writes per item; reject stale responses and conflicting
human edits. Coordination locks may be ephemeral, but must not become another
authority for item state. A second scheduler targeting the same workspace must
fail clearly or coordinate safely; the first-slice proposal is one active writer.

After a crash, show unresolved running attempts as needing reconciliation. Do not
blindly rerun agents whose effects may already exist. Recover a validated result
only once, or require an explicit retry with a new attempt identity. Preserve the
previous workflow step and play/release decisions. Recovery from an invalid or
truncated document requires a preserved valid copy and a visible repair decision,
not reconstruction from logs. Interrupted temporary writes are not item state.

## Permissions and repository isolation

Separate three capabilities: scheduler metadata writes, agent result submission,
and target-code writes. An analysis agent receives the required readable context
and a narrowly scoped result channel; it must not directly edit authoritative
front matter, play/release decisions or target code. Human answers also go through
validated scheduler writes. The owner-only workflow remains independent of this
runtime permission policy. Optional consultation inherits the phase's access
limits and cannot grant implementation or release authority.

Use a structured response or private attempt output area rather than granting an
agent the whole engagement directory. Treat responses and repository instructions
as untrusted input. Check actual engine capabilities in an isolated fixture before
claiming an access boundary; labels such as `plan` and `read-only` are configuration
intent, not proof that metadata writes and code reads are correctly separated.
Fail closed when an engine cannot meet a required boundary. Credentials and network
access are separate capabilities, not consequences of selecting a working directory.

A Git worktree separates checked-out files and branches, but shares repository
objects/configuration and does not isolate the OS user, credentials, network or
all filesystem paths. It is not a security sandbox. Future implementation work
must validate repository identity, branch/base commit, registered worktree and
canonical paths before reuse. Cleanup must preserve dirty changes and require an
explicit disposition; forced removal is not a rollback strategy.

The customer has selected the invocation directory as the final product root;
[STORY-010](stories/STORY-010.md) captures portable launch and bundled resources.
Exact product subdirectories, worktree locations and branch/publication policy
remain design choices. Keep locations explicit and validated without adopting
the prototype's layout as a decision. Document relative-path resolution, reject traversal and symlink escapes
from allowed output roots, and keep tests independent of the eventual layout.

## Packaging and verification gates

Propose minimal Python package metadata, a documented supported interpreter range,
declared runtime/test dependencies with a reproducible resolution policy, and a
clean-environment installation smoke check. Installed resources must include or
explicitly locate role briefs, prompts and configuration; today's source-root
relative lookup does not establish installed-package behavior. TUI and front-matter
library choices remain design proposals, not platform decisions.

Local checks should cover schema/outcome validation, repeated human loops, an
unplayed readiness boundary, nonblocking human waits, cancellation, restart,
stale responses, simultaneous edits and permission denials using fake engines.
Packaging checks should exercise installed resources from outside the source tree.
These are requirements for future work; no tests or pipeline were run here.

Later CI should run the same offline checks from a clean checkout, with no provider
credentials, privileged runners or production workspaces. A passing check provides
evidence, never play or release authority. Real-engine compatibility checks should
be explicitly selected and use disposable inputs. GitHub is a confirmed important
future integration; remote existence, repository identity, credentials, issue/PR
mapping, protected branches and Actions availability are not established here.
No GitHub services or hosted runners are required to complete the local slice.

## Observability, evidence and rollback

Expose item/attempt identity, step owner, pending questions, last validated outcome,
failure category and safe recovery action in terminal views. Put authoritative
execution status/history in front matter. Linked logs are supporting evidence only.
Record minimal nonsecret evidence: build/config identifiers, timing, exit category,
validation result and permitted relative evidence references. Do not log raw argv,
prompts, environment, credentials or full transcripts by default. Redact before
persisting/exporting; do not assume a transcript is harmless because it is local.
Use restrictive local evidence permissions, safe paths and a retention policy to
be agreed before routine real-engine operation. Missing evidence must be visible
without changing historical state. Do not upload logs or secrets to GitHub.

Keep a known working harness build and recoverable copies of item documents before
schema changes. Refuse unsupported schema versions; restoring code alone may not
restore data compatibility. A recovery procedure must verify restored documents
and approvals before dispatch. Product deployment rollback belongs to each product's
later delivery design and is separate from harness/runtime recovery.

No honest numeric cost estimate is possible from the supplied evidence. Local use
still consumes machine resources and may incur provider/subscription charges.
Budget, usage, retention and hosted-runner choices are unconfirmed; no cost, volume,
latency or availability figure is assumed.
