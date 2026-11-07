# 11: Choosing standards at ready

**What to build:** At `ready`, the TUI shows every available standard as a checklist, pre-ticked with the standards analysis chose and each one's reason. The customer can untick or add standards when playing the item. The choice replaces the item's `standards` requirement, so the implementer, tester and reviewer all see it; a standard the customer adds gets the reason "chosen by the customer". `ready` is the only customer step that writes a requirement field other than answers. Standards are the fifth customer input the TUI knows. The redesign is not complete without this.

**Blocked by:** 03, 06

**Status:** ready-for-agent

- [x] A journey test plays an item with one standard added and one removed, and finds the item's standards replaced, the added one with the customer reason
- [x] The implementer, tester and reviewer prompts for that item carry the chosen standards
- [x] A pilot test shows the checklist reaches the harness, without asserting on wording
