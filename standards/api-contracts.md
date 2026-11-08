---
name: api-contracts
kind: rule
description: Contract-first design of REST and GraphQL APIs, and the domain model and security that follow from the contract
---
- Contract first: define the contract (OpenAPI YAML, GraphQL schema) before
  the code, and generate code from it where that can be done sensibly.
- The contract is the window into the domain. Its resources, types and
  operations shape the domain model behind it, and who may perform each
  operation and what each response exposes are decided in the contract.
- One representation of a domain object: create, update and read use the
  same schema, not one per operation.
- The contract is the authority on what the application supports. It
  documents the behaviour even where code generation cannot honour it, such
  as scalar types, cross-field rules and security annotations some generators
  ignore.
- Where code generation is not available, the API tests use the contract
  definition to assert that behaviour meets it.
- Nothing speculative: error representations, pagination, filtering and the
  like are added only when the customer asks for them.
- Names in the contract come from the glossary. A term not in the glossary,
  or in the story's glossary changes, is not used.
- A story shows its API impact as a contract fragment in the spec's own
  format: new and changed paths and schemas only, with unchanged definitions
  referenced rather than repeated.
- A breaking change is stated in plain words beside the fragment.
- Any change to a public contract is made visible to the customer before the
  work is played.
- The reason for a contract decision the customer asked for goes in the
  contract's descriptions, so it outlives the story.
- Rules a linter can check (naming, pagination shape, required security
  schemes) belong to `devteam check`, not to this standard.
