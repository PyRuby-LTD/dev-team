# 13: Delete the remaining original harness and raise a PR to main

**What to build:** Everything the original harness had that nothing on the branch uses is deleted: the Markdown backlog, JSON workflows, question parsing, the original runner and CLI, the three role lens prompts (architect, platform engineer, quality lead), old prompts, and their tests. The README describes the redesigned harness. A pull request merges `redesign` into main. This is milestone 5.

**Blocked by:** 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12

**Status:** ready-for-agent

- [ ] No module, prompt, workflow or test from the original harness remains unless a step uses it
- [ ] The whole suite passes
- [ ] The README matches how the redesigned harness is set up and used
- [ ] A pull request from `redesign` to main is open
