# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`GLOSSARY.md`** at the repo root.
- **`docs/adr/`**: read ADRs that touch the area you're about to work in.
- **`Development patterns.md`** at the repo root: the author's own notes, in their own words, on what they value in development. It is source material for `roles/` and `prompts/`. Read it to understand intent; don't edit it unless asked, and don't record decisions in it.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill creates `GLOSSARY.md` lazily when a term is actually resolved.

## ADRs are rare

The code should mostly speak for itself. Write an ADR only for:

- a decision that is genuinely hard to reverse, or
- a surprising decision rooted in hard-won learning, which a future reader would otherwise "fix".

Everything else (ordinary design choices, things the code or tests already make clear, decisions that are cheap to revisit) gets no ADR. When in doubt, don't write one; ask the user.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `GLOSSARY.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders), but worth reopening because..._
