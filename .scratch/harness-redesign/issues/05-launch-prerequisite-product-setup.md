# 05: Product setup is checked as a prerequisite at launch

**What to build:** `dev-team` launched from any product directory acts on that product's backlog while using the harness's own workflows, prompts, briefs and configuration. Product setup (the backlog branch and a regression target) is a prerequisite checked at launch, not a workflow step; `dev-team init` still sets up an empty product. Initialisation code earns its place only as this prerequisite.

**Blocked by:** 01

**Status:** ready-for-agent

- [x] A test launches from a product outside the harness checkout and finds work items written to that product's backlog only
- [x] Launching in a product that is not set up reports what is missing and starts no agent
- [x] `dev-team init` in an empty repository sets it up; a second run changes nothing
