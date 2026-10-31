Fewer agents, opinionated standards, and story analysis at play time

I want fewer agents running one after another, with my opinions on specific
areas (API contracts and the domain model and security behind them, technical
writing and so on) supplied to the roles that need them. `Development patterns.md` holds the
opinions; this request is about the harness changes to deliver them.

## What I want

Standards:

- A standard is a file in the dev-team repository with a name, a one-line
  description and a kind: a lens (questions to ask, trade-offs to surface) or
  a rule (opinions to apply). It has to work with every engine, as the
  implementer runs on Codex.
- Some roles always get certain standards, e.g. the product owner and the
  publisher always get technical writing. This belongs beside the role's
  engine and model in `config/roles.toml`.
- During story analysis the product owner proposes the standards a story
  needs, and the challenger can dispute them.
- At `ready` the TUI shows me every standard, the proposed ones ticked and the
  rest not, and I toggle them. Always-on standards show as ticked and locked.
  The story records my final selection, not the proposal, so the recorded
  work item in the PR shows which standards the work was held to.
- Every later role on the story gets the selected standards. The challenger
  gets the same standards as the product owner.

Advisers become lenses:

- The architect, platform engineer and quality lead stop being agents. Their
  briefs and request-analysis prompts become lens standards that always apply
  to the product owner during request analysis.
- The request workflow becomes the product owner with its questions loop,
  then my review. No challenger: request analysis only drafts items.
- `roles/analyst.md` goes; the product owner already owns story analysis.

Two kinds of analysis:

- Request analysis works on the idea: problem, audience, boundaries and how
  the work splits into epics, stories, bugs and tasks. It leaves draft items
  with a statement, rough scope and first-pass glossary and persona changes,
  not final acceptance criteria. The request prompt currently demands
  concrete criteria and implementation-ready requirements; that moves to
  story analysis.
- Story analysis happens when I play the story, against the codebase with its
  dependencies merged, so the story flow becomes roughly
  `captured --play--> dependencies -> analysis <-> answering -> challenge ->
  ready -> implement`. Today `play` is at `ready`.

Shared material every role needs:

- The product's `glossary.md` and personas file, and the writing standard,
  reach every role that uses them.

Implementer and reviewer flow:

- The implementer can raise a tech task (backlog capture in its prompt and
  allowed tools).
- Order: implementer, reviewer, tester when the reviewer asks for one,
  reviewer again. The tester returns to the implementer when a test fails
  because of the implementation, and to the reviewer when tests pass.

Examples:

- `prompts/examples/` holds an example of each work item and agent response,
  so each prompt shows what to produce rather than describing it. Today
  nothing supplies them to any role.
- Each step gets the examples for what it produces: request analysis gets the
  draft story, epic, bug and task; story analysis gets the analysed story; the
  implementer gets the task, as it can raise tech tasks; the challenger,
  reviewer and publisher get their own responses.
- The examples match the record schemas from STORY-030 and the result shape
  from STORY-028, so an agent following one produces something that
  validates. Today their field names differ from STORY-030's.

## Things to settle

- Whether a standard says which roles it applies to, or every selected
  standard reaches every later role.
- Whether I can change the selection at `accept` as well as `ready`.
- Whether a product repository can add or override standards for decisions
  specific to it.

## Existing backlog this touches

- STORY-034 puts the dependency wait between `ready` and `implement`; on this
  model it comes before story analysis.
- STORY-028 and STORY-029 give each adviser step in `workflows/analysis.json`
  its own reads and writes; those steps go.
- STORY-030's record fields and migration lack glossary changes, persona
  changes and the selected standards, and refuse unknown headings.
- Tests in `tests/test_questions.py` pin the `**Answer:**` sentence in the
  analysis prompts and will need loosening when the prompts are rewritten.
