# 12: Concurrency for steps that do not hold the checkout

**What to build:** Agent steps that do not hold the checkout, such as request analysis and story analysis, run while another item holds the checkout, and several of them run in parallel. Steps that hold the checkout still queue for it one at a time. This is milestone 4.

**Blocked by:** 07

**Status:** ready-for-agent

- [ ] A journey test analyses a request while another item's implementer holds the checkout, with both progressing
- [ ] Two items' analysis steps run at once and both are recorded correctly, with no lost writes to the backlog
- [ ] Checkout-holding steps never overlap
