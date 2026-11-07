# 12: Concurrency for steps that do not hold the checkout

**What to build:** Agent steps that do not hold the checkout, such as request analysis and story analysis, run while another item holds the checkout, and several of them run in parallel. Steps that hold the checkout still queue for it one at a time. This is milestone 4.

**Blocked by:** 07

**Status:** ready-for-agent

- [x] A journey test analyses a request while another item's implementer holds the checkout, with both progressing
- [x] Two items' analysis steps run at once and both are recorded correctly, with no lost writes to the backlog
- [x] Checkout-holding steps never overlap

## Comments

The run loop starts each pending step on its own thread and starts a step that holds the checkout only when no other checkout step is running; an item skipped for that is shown waiting for the checkout. When nothing is running, the item already on the checkout goes first, so an item waiting for the checkout cannot keep taking its turn. Backlog writes were already serialised by the backlog lock, so recording needed no change. Stopping the loop does not wait for running agents, as before: the TUI's harness thread was already a daemon.

The scripted engine stub takes a plan keyed by a word from each item's title, so parallel items each follow their own entries.
