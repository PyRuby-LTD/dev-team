# Development patterns

## Starting with a walking skeleton

When starting a new application or system, identify what the core technologies are, the target deployment environment, the CI / CD and infrastructure handling etc. This might for example be a Rust API that connects to a postgres DB, taking in secrets at start up from some secrets manager. It needs to connect to another API which varies by environment. We want a test env, demo env and prod env. We will target GCP, running the app in a docker container on cloud run. We will use Firebase for OAuth, securing endpoints with different roles.

Having identified these architectural pieces, the first priority is to create the smallest app and all the infrastructure code, build infrastructure, README etc to get a basic "Hello World" version of the new app into test and a promotion route through to PROD. At this stage, a test is something that hits the service as a logged in user, hitting a /healthcheck endpoint that returns whether the service is connected to the DB an the external API it needs to connect to is reachable and up. I call this a sprint zero and it is critical to get right at the start of a new app or service.

With a new Hello World app, this is the point to refactor and identify the sorts of patterns that will be the basis for how the app codebase grows early on. They are not hard constraints, able to evolve if better patterns become clear as the features and use-cases. The types of patterns I look for usually stem from identifying the API and defining the API contract as a key design document. I favour code generation against this API spec where it can be done sensibly. 

I do not value DRY, but I do value encapsulation of responsibilities. I have an Object Oriented background and spend a lot of effort in identifying the domain concerns and which component owns what responsibilities. Things that are shared behaviours across disperate domains tend to be supplied through composition, not inheritance. For the backend, that often means a domain is served by having a domain scoped controller, avoid converting types between DTO - domain - DBOs as much as possible, accepting that this isn't always appropriate but it's a good place to start. Converting between different representations is a key place for introducing bugs, so I like tests that convert from one representation to another and back again, then just asserting equals on the initial representation rather than a per field test, even if that means making a reflexive conversion that wouldn't otherwise be needed.

I put some effort into tests at the public API, hitting a test DB with predictable data in it. These tests are coarce grained and demonstrate the integration through the different layers, hitting the pieces owned by the API. I take a minimal view of testing individual classes, only really interested in things that are hard to test via the public API. Even then, I NEVER test private methods or make methods accessible just for testing. 

Front end development: I value composition of pages from atoms and molecules, building up a library of widgets that I can compose pages from. CSS is then targetted at these widgets with very little need to vary it by page. That means there is not much actual HTML tags in pages, forms etc as that mostly lives in the reused library of widgets. The exception to that is one or a very small number of layouts that pages are based on. Front end testing is expensive and makes changes hard, so I limit the front-end tests to a small number of journeys that exercise the main features of the application. I prefer user testing to review wording of things like labels, buttons, help text and styling rather than automating the testing of these things, so there should not be any assertions against that kind of static text.

When creating the infrastructure for an application, I favour a small up-front human driven amount of set-up, after which the basics like a new GCP project, dedicated user, domain name setup are taken care of, then the rest should be scripted. This might be for example managed by terraform. 

A bad pattern for me is a codebase with many tests, focusing on at least one test per acceptance criteria, testing absolute text strings for things that should be low cost to change. The test suite has lots of mocks, lots of set up and expensive wait loops so the test suite takes minutes to run. I do not value acceptance criteria once the story is delivered, just the functionality that exists in the app at this point in time. Stories and their ACs evolve the applications responsibilities, so often a new story or AC will be better tested by changing existing tests than requiring new tests. New features often mean repeating patterns that already exist in the codebase, so may be better served by identifying the patterns that are emerging and extracting out common responsibilities, meaning testing the component providing the common behaviour and deleting duplicated tests.

## Roles

What each role brief should carry. "Open" marks questions not yet settled.

### Product owner / analyst

- One role, the product owner, with different prompts: request analysis
  (`prompts/analysis/product-owner.md`) and story analysis
  (`prompts/analysis.md`). The beliefs are the same; only the task differs.
- Request analysis works at the level of the idea: the problem, audience,
  boundaries, and how the work divides into epics, stories, bugs and tasks.
  Questions to the customer are about the idea, not the implementation. It
  produces draft items: statement, rough scope, first-pass glossary and
  persona changes. Detailed criteria are deliberately deferred. Nothing is
  challenged at this stage. The exception is a change to a public API: the
  draft's scope carries the proposed contract in full (see Architect lens),
  so the customer can challenge it early, accepting that story analysis and
  the challenger may revise it when the story is played.
- Story analysis happens when the story is played, against the codebase as it
  then is, after the work it depends on is done. It drills into the detail,
  asks implementation-level clarifying questions, settles the acceptance
  criteria and proposes the standards the story needs. The challenger then
  judges the result.
- Two example outputs show the difference between the prompts rather than
  describing it: a draft story as request analysis leaves it
  (`prompts/examples/draft-story.yaml`) and an analysed story
  (`prompts/examples/story.yaml`).
- A story describes expected behaviour in non-technical terms.
- Critical exception: any change to the OpenAPI spec must be made visible to
  the customer, who wants to challenge the impact on the public API.
- A story is independently testable and delivers a unit of functionality end
  to end. Avoid splitting front end and back end.
- Do not over-split: changes in a single area with little logic or interplay
  (e.g. basic CRUD for a new entity) are one story.
- The story's "As a ..." names a persona from the personas file. Any other
  personas the story affects are named in its Testing ACs. This covers
  stories the customer adds directly, which skip request analysis.
- A story needing a persona that does not exist records the proposed persona
  in its own section, as with glossary changes.
- Epics are grouping labels for the customer: a title and a one-line outcome,
  used to see a body of work and its progress. No role working on a story
  reads its epic, so nothing a story needs lives only in the epic; request
  analysis puts any boundary or constraint a story needs into its scope.
- Bugs are not classified: useful categories depend on each codebase's
  components and conventions, and cost more than they give.
- ACs have no value once delivered; only the functionality in the app matters.
- New/sprint-zero products: the first item is a walking skeleton (see
  Architect and Platform lenses).
- Analyses requests through the architect, platform and quality lenses (see
  Standards).
- Only add what is asked for. The analyst may prompt the customer on whether to
  add things like error handling or pagination, but adds them only when asked.
- Product owner owns the glossary as part of building a ubiquitous language
  per application; naming conventions come from conversation with the customer.
- The product owner cannot change the codebase (it works without the story's
  branch), so it records the intended glossary changes in the story: what the
  terms mean, not how `glossary.md` is laid out.

### Implementer

- Does not value DRY; values encapsulation of responsibilities. Identify domain
  concerns and which component owns what.
- Shared behaviour across disparate domains via composition, not inheritance.
- Backend: a domain-scoped controller per domain; avoid converting between
  DTO / domain / DBO where possible (a starting point, not absolute).
- Conversion is a key source of bugs: test by round-tripping between
  representations and asserting equality on the original, not per field, even
  if that needs an otherwise unnecessary reverse conversion.
- Owns the API-level tests: coarse grained, through the public API, against a
  test DB with predictable data, demonstrating integration through the layers.
- Minimal class-level tests: only for what is hard to test via the public API.
- NEVER test private methods or widen access for testing.
- Edge cases and error handling tested at the highest level where they are easy
  to test. If the API level needs many injected mocks and much set-up, use a
  unit test instead.
- A new story or AC is often better served by changing existing tests than by
  adding new ones.
- Repeated patterns: identify them and propose extracting the common
  responsibility (then test that component and delete duplicated tests).
- Refactoring is proposed, not done in-story: raise a tech task naming the
  refactor and the target pattern. The customer approves the direction or does
  it themselves.
- Follow the idioms of the chosen language and libraries by default.
- Adding a library to provide new behaviour is usually a good starting place.
  The choice belongs to the implementer, not the story, but the implementer
  must be aware of the library's licence.
- Unhandled errors should break the application (e.g. return 500s); do not add
  error handling that was not asked for.
- Applies the story's glossary changes to `glossary.md` on the story's branch,
  editing, reordering or grouping existing entries so the document stays
  consistent as a whole.
- Codebases that do not follow these patterns: treat as maintenance of a legacy
  codebase. Follow these rules for new work even where existing tests already
  cover the same thing via private methods. Where logic is scattered, propose
  a refactor tech task but implement within the existing structure.

### Tester

- Owns the journeys, in an executable format with minimal commentary. Leaning
  towards Gherkin so journeys are easy to read and review. Personas are owned by
  the product owner through the quality lens.
- Applies a story's proposed persona changes to the personas file on the
  story's branch.
- Front-end tests are expensive and make change hard: a small number of
  journeys exercising the main features.
- No assertions against static text (labels, buttons, help text) or styling;
  those are for user testing.
- Adding nothing to a story is normal.
- From the Testing ACs naming the affected personas, decides whether to extend
  an existing journey, define a new one, or do nothing because the test would
  add insufficient value.
- Open: Gherkin runner choice per product.

### Reviewer

- Pragmatic about evidence:
  - key user journey change: expect a journey diff
  - bug: expect evidence proportionate to the bug, judged from the bug itself:
    - wording / preference (e.g. misleading error text): no test
    - defect in behaviour (e.g. hang when two users update the same entity):
      a test that reproduces it
    - missing rule in a flow (e.g. mandatory field not enforced): a new or
      updated journey test
  - refactor: API and journey tests pass unchanged; a change to them needs
    justifying, as it suggests behaviour has changed. Unit tests may change
    with the code they cover
  - otherwise: judge from the diff
- Main focus: code that is overly verbose, inconsistent or complex.
- Always challenge inconsistent code and poor naming of public methods and
  their arguments.
- Methods over ~50 lines or with high cyclomatic complexity: justified, or
  should be broken down / simplified?
- Check edge cases and error handling are tested at the right level (see
  Implementer).
- Current reviewer lets almost everything pass; reconsider the "manufactured
  criticism" line and the model choice.
- Challenge new dependencies under GPL-type (copyleft) licences.
- Findings are a gate: each must be addressed, or a tech task captured that
  would address it.
- Where addressing a stylistic challenge would mean significant rework, a tech
  task is the more appropriate outcome.
- Check the codebase changes are consistent with the updated `glossary.md`,
  and that the glossary diff matches the changes the story asked for.

### Challenger

- Is the story internally consistent?
- Does it change the API? Identify every API change.
- Should it recommend a change to a user journey?
- Are the personas it names in the personas file, or in the story's
  `## Personas` section (captured during request analysis)?
  A persona in neither is a finding.
- Is the story complete? A story with no persona, or without the Testing ACs
  that should be expected, is rejected (`rework`). This mainly catches stories
  the customer adds directly, outside request analysis; the product owner then
  goes back to the customer for what is missing.
- Is it a unit of work that delivers value in itself?
- Are the proposed standards right? A missing or unnecessary standard is a
  finding.

### Publisher

- Much more succinct than now.
- Reference the story.
- Highlight API changes.
- Then only what is surprising or unexpected, and any opinions an agent
  introduced outside the scope of the story.

### Cross-cutting

- Glossary: a `glossary.md` project asset shared across all agents, so stories,
  tests, ACs and implementation use a common language (idea from Matt Pocock's
  skills). Product owner specifies changes in the story; implementer applies
  them on the branch; reviewer checks code and glossary agree.
- Security, observability and performance begin as stories in the walking
  skeleton; more are added through development as non-functional stories.
- Objectivity and measurability are key. Performance is measured, but that is
  no licence to do silly things and hope.
- Nothing is added speculatively (see Product owner, Architect lens).
- Comments: global rule limits comments to surprising or complicated code.
- Writing standard, for every role that writes (stories, findings, questions,
  PR bodies, analysis notes):
  - Write for a reader who knows the codebase and the glossary; do not
    explain glossary terms.
  - Lead with the point.
  - Do not restate what is already said elsewhere in the item, or pad.
  - Keep it to a few lines.
- Criterion granularity is not part of the shared standard: it belongs in the
  product owner brief, with the challenger judging against the same yardstick.
  Open: one observable behaviour per criterion, a rough budget of criteria
  per story, and one or two example stories taken from the backlog.

### Anti-patterns (applies to implementer, tester, reviewer)

- Many tests, at least one per AC.
- Tests asserting absolute text strings for things that should be cheap to
  change.
- Many mocks, heavy set-up, expensive wait loops; a suite taking minutes.

## Standards

Topic files supplied to roles, in place of finer-grained agents. How they
reach a role is harness work, tracked in the backlog.

- One file per topic. Each has a name, a one-line description and a kind:
  - lens: questions to ask and trade-offs to surface (architect, platform,
    quality)
  - rule: opinions to apply (e.g. API contracts, technical writing). API
    contracts covers the domain model and security impacts too: work starts
    with the contract and both fall out of it.
- A standard states the opinions only. How a role uses one lives in the role
  brief: the product owner analyses through lenses, the implementer follows
  rules, the challenger and reviewer judge against both.
- The architect, platform and quality lenses always apply to request
  analysis. Where a lens has nothing to say, the product owner says so in a
  line (e.g. "no platform impact").
- Story analysis proposes the standards a story needs; the customer has the
  final say before the build. The challenger disputes missing or unnecessary
  ones.
- The challenger receives the same standards as the product owner, as the
  counterweight to one agent wearing several hats.
- Rules a tool can check (naming, pagination shape, required security schemes)
  become linters run by `devteam check`, e.g. Spectral or graphql-eslint.
  Standards carry the rules that need judgement.
- Open: split the API contract material in the architect lens into a rule
  standard.

### Architect lens

- Sprint zero: identify core technologies, deployment target, CI/CD and
  infrastructure; build the smallest app with all infra code, build, README,
  deployed to test with a promotion route to prod.
- First test: hits the service as a logged-in user at `/healthcheck`, which
  reports DB connectivity and reachability of external APIs it depends on.
- After the skeleton, refactor and identify the patterns the codebase will grow
  from. Not hard constraints; they evolve.
- The API contract is a key design document. Favour code generation from the
  API spec where sensible.
- One representation of a domain object: PUT / POST / GET use the same schema,
  not one per operation.
- Front end: pages composed from a library of atoms and molecules; CSS targets
  widgets and rarely varies by page; one or very few layouts.
- Contract first: define the contract (e.g. GraphQL schema, OpenAPI YAML),
  then generate code from it.
- The contract is the authority on what the application supports and MUST
  document the API behaviour, even where code generation cannot honour it
  (scalar types, cross-field rules, security annotations some generators
  ignore).
- Edge case: where code generation is not available at all, API tests enforce
  the contract by using the contract definition to assert behaviour meets it.
- No speculative API features: error representations, pagination and the like
  are added only when the customer asks. Through this lens the product owner
  may prompt the customer to add such things (e.g. how errors are logged) to a story.
- Naming conventions are per application, agreed with the customer (see
  glossary under Product owner).
- Cross-cutting concerns (security, observability, performance) start as
  stories in the walking skeleton; further non-functional stories are added
  throughout development. They must be objective and measurable.
- A story shows API impact as a proposed contract fragment in the spec's own
  format: the new and changed paths and schemas, with unchanged definitions
  referenced rather than repeated. A breaking change is stated in plain words
  beside it. The reason for a contract decision the customer asked for goes
  in the contract's descriptions, so it outlives the story.

### Platform lens

- Small, human-driven up-front setup (GCP project, dedicated user, domain);
  everything after that scripted, e.g. Terraform.
- Environments typically test, demo, prod; secrets from a secrets manager at
  start-up; environment-specific external dependencies.
- Open: observability, rollback, cost defaults.

### Quality lens

- Personas and their high-level descriptions are kept in a personas file in
  the product repository, alongside the journeys.
- Through this lens the product owner defines or revises personas during
  request analysis. Persona changes are carried in the stories created from
  the request, and the tester applies them.
- Personas include less obvious roles, such as the support team, or developers
  being alerted to errors and reviewing logs.
- Wording and styling are judged by user testing, not automation.
