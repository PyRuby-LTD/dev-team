# 02: The TUI shows the YAML backlog and records outcomes, feedback and new requests

**What to build:** A rebuilt terminal UI over the YAML backlog. It lists every YAML work item grouped under its epic, with its step and who that step is waiting on; filters to items waiting on the customer; lists an invalid file with its error while the rest load; and ignores the original Markdown items. An item's detail view is rendered from a Jinja template, using the same environment and filters as prompts, with the item, its current step, the workflow and the step's pending input as context, shown as Markdown. On a customer step, the customer chooses an outcome from a list showing each outcome's meaning; when the step's output has a `feedback` field, a free-text feedback box is offered. The customer can capture a new request as free text. The harness loop runs in the background, so choosing `analyse` invokes the product owner. A workflow whose customer step declares an output field other than the known inputs (`questions`, `feedback`, and later `standards`) is rejected at load. The original TUI is a reference for interactions only.

**Blocked by:** 01

**Status:** ready-for-agent

- [x] A small number of pilot tests show the TUI opens on a backlog and that choosing an outcome, giving feedback and capturing a new request each reach the harness, asserting on the resulting work items, not on labels or layout
- [x] Editing the detail template changes what is displayed with no code change
- [x] A customer step declaring an unknown output field makes the workflow fail to load with a clear reason, tested at the command seam
- [x] The original TUI module and its tests are deleted
