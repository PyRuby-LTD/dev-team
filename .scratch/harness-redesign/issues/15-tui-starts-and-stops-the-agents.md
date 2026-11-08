# 15: The customer starts and stops the agents from the TUI

**What to build:** The TUI opens with the harness loop stopped, so nothing is handed to an agent or the harness until the customer presses `s`. Pressing `s` again stops the loop from starting any further steps, while any step already running finishes and is recorded as usual. The TUI shows whether the agents are running, stopping (naming the items still running) or stopped. Customer outcomes, feedback and new requests are recorded whether or not the agents are running; an item moved to an agent step while they are stopped waits there until they are started. The original TUI is the reference for this interaction.

`Harness.run` already checks its stop event between steps, so a step in progress is never interrupted; the work is in the TUI. When concurrency arrives (12), stopping must also stop new parallel runs from starting while letting running ones finish.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] A pilot test shows that with the agents stopped, choosing `analyse` leaves the request at `analysis` and no engine runs; after pressing `s`, the product owner runs and the request moves on, asserting on the resulting work item
- [ ] A pilot test shows that pressing `s` while a step is running lets that step finish and be recorded, and no further step starts
