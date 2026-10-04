# Proposed delivery plan

Owner: delivery manager. Date: 2026-10-02. Status: draft for customer selection.

This is a dependency sequence, not customer-selected priority or permission to
play. The front matter of each epic/story is authoritative for its current state
and dependencies. Implementation has not started.

## First increment: the team can analyse its own work

The customer can capture a proposed item, ask the owning analysis agent to work
on it, answer its questions in the terminal, and see it stop at ready-to-play.
Other eligible items can progress while one waits. The coordinator can restart
without blindly launching duplicate work. No implementation starts as a side
effect of an analysis response.

Proposed build order:

1. Establish the Markdown/front-matter contract, validation, stable identities,
   hierarchy and safe updates. Preserve narrative and existing records.
2. Validate versioned workflows and named responses; enforce single ownership,
   defined targets, revisions and explicit human transitions.
3. Dispatch a fake owning agent through a durable attempt, receive questions,
   expose a human request, submit answers and complete another analysis turn.
4. Add recovery and bounded scheduling so a waiting/failed item does not stop
   unrelated work or trigger duplicate external effects after restart.
5. Expose the same records and actions through a minimal TUI, with a limited
   live analysis pilot using a verified existing role/engine profile.

The product owner's story dependencies refine this order. Automated checks and
acceptance evidence belong with each story, not in an unowned final test phase.

## Story sequence and handoffs

| Story | Outcome | Depends on |
|---|---|---|
| [STORY-001](stories/STORY-001.md) | Capture and validate linked Markdown records | none |
| [STORY-002](stories/STORY-002.md) | Preserve state across writes and conflicts | STORY-001 |
| [STORY-003](stories/STORY-003.md) | Preview/import legacy work without destroying originals | STORY-001, STORY-002 |
| [STORY-004](stories/STORY-004.md) | Validate owner-only workflows and named outcomes | STORY-001 |
| [STORY-005](stories/STORY-005.md) | Drive analysis through durable human questions | STORY-002, STORY-004 |
| [STORY-006](stories/STORY-006.md) | Reconcile interrupted attempts and reject stale responses | STORY-005 |
| [STORY-007](stories/STORY-007.md) | Inspect backlog and current responsibility in the TUI | STORY-001, STORY-004 |
| [STORY-008](stories/STORY-008.md) | Request analysis and submit answers in the TUI | STORY-006, STORY-007 |
| [STORY-009](stories/STORY-009.md) | Explicitly authorise a ready revision at a held delivery boundary | STORY-008 |
| [STORY-010](stories/STORY-010.md) | Launch the bundled team from any product directory, including an empty repository | STORY-007 |

STORY-003 can proceed independently of the later controller work once persistence
is available; it is not a prerequisite for starting workflow design. STORY-007
can begin with validated fixture records before the full analysis loop exists.
The three detailed epics group these stories; the three deferred epics preserve
the subsequent product journey. No detailed task records are needed yet.

## End-to-end customer demonstration

1. Open this harness backlog; inspect an epic and its child stories.
2. Capture or select a sample story without starting implementation.
3. Request analysis. Observe the owning role and attempt status.
4. Have the fake agent ask a question; observe one persistent human request.
5. Leave that question pending and analyse an unrelated item.
6. Save a partial answer, then explicitly submit a complete response.
7. Observe the item return to the same owning analysis role with prior answers.
8. Reach ready-to-play. Prove implementation has not been invoked.
9. Close/reopen the TUI and restart the coordinator. Confirm state is recovered
   from the Markdown files; ambiguous in-flight work is surfaced for recovery.
10. Explicitly play one ready revision and see its recorded authorisation held
    at the delivery hand-off; real implementation remains unavailable until the
    later delivery capability. Assert zero implementation invocations.

Follow with a separately selected live analysis pilot once its engine, permissions
and product context are verified. The scripted demonstration does not establish
live engine compatibility by itself.

## Later increments

- Integrate GitHub PRs and real test/review evidence, and extend the flow through
  implementation, test development, review, integration and automation.
- Track exact staging candidates and customer UAT, then separately authorised
  releases and release communications.
- Extend product onboarding to generate a walking skeleton, infrastructure and
  pipelines from customer constraints; reuse team definitions across products
  with product-specific specialist roles.

These remain named epics in [scope.md](scope.md). They are not dropped from the
product vision and are not detailed prematurely for the first analysis-loop slice.

## Using the existing team to build the next version

Use the current role charters to refine a selected story and review its criteria.
Until the new loader exists, do not invoke `devteam run` on these Markdown IDs:
the legacy pipeline understands ITEM directories and can move from investigation
straight into implementation. After an explicit customer play decision, bridge
one selected story's criteria into a controlled implementation session, retaining
its Markdown identity and evidence links. Do not treat two representations as
independently editable backlog sources.

The first slice must preserve/import any real legacy items without interpreting
legacy `done` as proof of deployment or release. Updating the running harness
while it controls work must happen at a quiescent boundary, not mid-attempt.
