<!--
Destination: docs/project/slices/MM-NN-{slice-slug}.md
Naming: MM = Milestone Number (e.g. 01, or 00 for ad-hoc). NN = Sequential Slice Number.
-->

# Slice: {{Feature Name}}
- **Status:** [Planned | In Progress | Completed]
- **Milestone:** [link]
- **Depends On:** [link]
- **Specs:** [links]
- **Prototype:** [link]
- **Component Docs:** [links]
- **Scope Slug:** `feature-slug`  <!-- 1-2 kebab-case words only. -->

## Goal
1-2 sentences describing the user need and measurable value delivered by this slice.

## Context
Key findings, existing contracts, and technical constraints discovered through static code reading or library documentation.
- `ComponentName`: Description of existing contracts, internal interfaces, or invariants.
- `LibraryName`: Description of external dependency behavior, configuration, or API signatures.

## Scenarios
Primary user journeys and happy paths. These drive End-to-End Acceptance Tests in the Wiring deliverable.

> As a [user type], I want to [action] so that [benefit].

```gherkin
Given [precondition]
When [action]
Then [expected outcome]
```

## Edge Cases
Boundary conditions, errors, and validation edge cases. These drive granular Unit Tests in Core deliverables.
- **Title**: If [condition], then [behavior], because [reason/invariant].

## Key Unknowns

**Format:**
- [ ] [Tag] Title: Description of the unknown. Design Sensitivity.

**Taxonomy:**
- `[Domain]` = Ambiguities in business rules, policy decisions, domain definitions, or scope boundaries. Resolve by asking the user directly.
- `[Technical]` = External dependencies, third-party libraries, APIs, internal state machines, complex algorithms, concurrency, performance, or data storage. Resolve via works-like prototypes. Do not log items that can be verified through static code reading or library documentation; resolve and record those under Context instead.
- `[Functional]` = User-facing ergonomics, CLI flags, terminal rendering, interactive flows, or layout aesthetics. Resolve via looks-like prototypes.

**Mandatory De-risking Triggers (must include, but are not limited to):**
1. Log any new or modified integration with an external system, library, API, or storage layer as `[Technical]`.
2. Log any new or modified user interaction, CLI flags, terminal formatting, or interactive UX flow as `[Functional]`.
3. Log any business rule, policy, or scope ambiguity as `[Domain]`.

**Design Sensitivity:** For every unknown, record a one-line Design Sensitivity stating how the design reacts to each resolution (e.g., "if this resolves as X → contracts hold; if Y → this port/DTO changes").

## Impact
Map affected components using non-breaking steps (expand -> migrate -> contract) to protect existing consumers.

**Format:**
1. `[NEW]` `ComponentOrModule` — Create new boundary or component.
2. `[EXPAND]` `ComponentOrModule.method` — Additive, non-breaking contract extension alongside existing code.
3. `[MIGRATE]` `ConsumerComponent` — Transition consumers one by one to use the expanded contract.
4. `[CONTRACT]` `ObsoleteComponentOrMethod` — Safely remove deprecated methods, shims, or dead code once all callers have migrated.

## Deliverables

**Types:**
- **Env:** Declarative tooling, build files, CI workflows, hooks, or package dependencies.
- **Interface:** Signatures, ports, interfaces, DTOs, and schemas. Expands shared contracts additively so existing callers remain unbroken.
- **Harness:** Shared test infrastructure (drivers, observers, in-memory fakes, and fixtures).
- **Wiring:** Outermost boundary tracer bullet connecting entry points with skeleton responses using defined interfaces and harness doubles.
- **Core:** Domain entities, business rules, workflows, and algorithmic invariants driven by unit tests.
- **Adapter:** Real infrastructure implementations (filesystem, CLI, subprocess, database, external protocols) driven by integration tests.
- **Migration:** Adapting existing callers across the codebase to use newly expanded contracts, updating their caller tests.
- **Refactor:** Improving code design without altering behavior. Requires no new tests; existing tests remain green.
- **Cleanup:** Contracting shared seams by removing deprecated methods, dead code, and temporary shims once callers have migrated.

**Order:** Order deliverables to keep all tests passing at every commit (`make test`). Include Env before Interface only when tooling or package prerequisites must exist for tests to run:
`(Env) -> Interface -> Harness -> Wiring -> Core -> Adapter -> Migration -> Refactor -> Cleanup`

**Tests:** Do not specify individual tests in deliverables. Scenarios and Edge Cases must define test requirements.

**Format:**
- [ ] **Interface** - Define port interfaces, DTOs, and schemas.
- [ ] **Harness** - Build or update shared test doubles and fixtures.
- [ ] **Wiring** - Connect outermost boundaries with skeleton response using defined interfaces and harness doubles.
- [ ] **Core** - Implement domain logic and invariants.
- [ ] **Adapter** - Implement infrastructure adapter.

## Implementation Notes
Free-form notes recording decisions, deviations, or discoveries during implementation.

## Verification
Manual verification steps for user execution at slice conclusion. Provide clear instructions with copy-pasteable commands or interactive UI steps. Do not include automated test commands.

**Format:**
1. **Title:**
   Run `command <args>`.
   Verify output contains `expected output`.
2. **Title:**
   Navigate to `[View/Screen]`.
   Trigger `[Action]`.
   Confirm `[Observed State/Element]`.
