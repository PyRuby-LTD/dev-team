# Problem and intended outcomes

Source: [authoritative customer brief](brief.md). This engagement analyses the delivery harness itself; it does not authorise implementation.

The customer wants to describe a product and subsequent features, let existing agent roles analyse them, answer questions as needed, and choose when ready work is played and when releases reach users. Today the Python prototype has a fixed pipeline, sibling JSON state and a CLI; inspection of devteam/workitem.py, pipeline.py and cli.py shows no separate customer play gate between investigation and implementation. This is a capability gap, not evidence of measured customer losses.

The primary audience is the customer operating the reusable team. Agent role owners need reliable hand-offs and enough context to analyse work. Audience size, concurrent operators, backlog volumes and response-time targets are unknown; no budget or delivery date has been agreed.

Success for the proposed first slice means a customer can capture a feature, see its epic/story hierarchy, answer multiple rounds of analysis questions, return after interruption, and distinguish ready work from authorised work. Another eligible item can progress while one awaits an answer. Repeated inputs cannot create duplicate transitions or human requests. Customer play is explicit and release remains separately controlled.

Confirmed boundaries: Markdown front matter is the sole authoritative work-item state; no database or authoritative sibling state.json. Each workflow step has exactly one owning agent or human, with no collaborators field. An agent may independently consult other roles. Python validates named outcomes before committing transitions.

First-slice non-goals proposed by the product owner: implementation execution, GitHub/CI automation, staging deployments, releases, general sprint-zero generation and specialist provisioning. These remain named deferred epics. No storage branch strategy is selected.

See [capabilities](capabilities.md), [scope and separately recorded proposals](scope.md), and the intended colleague-owned [architecture](architecture.md), [qualities](qualities.md) and [quality strategy](quality-strategy.md). Those design documents are dependencies for refinement, not presumed approved contracts.
