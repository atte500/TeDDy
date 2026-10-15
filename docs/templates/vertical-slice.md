# Slice: {{feature_name}}
- **Status:** [Planned | In Progress | Completed]
- **Milestone:** [link]
- **Specs:** [links]
- **Prototype:** [link]
- **Component Docs:** [links]
- **Scope Slug:** `feature-slug`  <!-- 1-2 kebab-case words only. -->

## Business Goal
1-2 sentences describing the user need and measurable value delivered by this slice.

## Scenarios
> As a [user type], I want to [action] so that [benefit].

```gherkin
Given [precondition]
When [action]
Then [expected outcome]
```

## Edge Cases
- **Title**: If [condition], then [behavior], because [reason/invariant].

## Key Unknowns

**Taxonomy:**
- `[Domain]` = Ambiguities in business rules, policy decisions, domain definitions, or scope boundaries. Resolve by asking the user directly.
- `[Technical]` = External dependencies, third-party libraries, APIs, internal state machines, complex algorithms, concurrency, performance, or data storage. Resolve via works-like prototypes.
- `[Functional]` = User-facing ergonomics, CLI flags, terminal rendering, interactive flows, or layout aesthetics. Resolve via looks-like prototypes.

**Mandatory De-risking Triggers (must include, but are not limited to):**
1. Log any new or modified integration with an external system, library, API, or storage layer as `[Technical]`.
2. Log any new or modified user interaction, CLI flags, terminal formatting, or interactive UX flow as `[Functional]`.
3. Log any business rule, policy, or scope ambiguity as `[Domain]`.

**Design Sensitivity:** For every unknown, record a one-line Design Sensitivity stating how the design reacts to each resolution (e.g., "if this resolves as X → contracts hold; if Y → this port/DTO changes").

**Format:**
- [ ] [Tag] Title: Description of the unknown. Design Sensitivity.

## Scope & Impact
Surface of affected components classified by the Parallel Change model:
- `[NEW]` `ComponentOrModule` — role and responsibility
- `[EXPAND]` `ComponentOrModule.method` — additive/non-breaking extension
- `[MIGRATE]` `ConsumerComponent` — updating callers to new contract
- `[CONTRACT]` `ObsoleteComponentOrMethod` — removal of retired code/shims

## Deliverables

**Types:**
- **Env:** Declarative tooling, build files, CI workflows, hooks, or config templates.
- **Wiring:** Outermost boundary tracer bullet returning skeleton/fake data to connect layers end-to-end.
- **Contract:** Signatures, ports, interfaces, DTOs, domain models.
- **Harness:** Modifying or extending shared test infrastructure (Drivers, Observers, Fakes, Setup fixtures).
- **Logic:** Core domain logic and business rules driven by unit tests, systematically replacing skeleton returns and temporary fakes with real implementations.
- **Migration:** Adapting existing consumers to new contracts.
- **Refactor:** Improving code design without altering behavior (DRY, SRP, extracting helpers).
- **Cleanup:** Removing deprecated methods, dead code, and temporary shims.

**Order:** Order deliverables to maintain a Continuous Green State (`make test` passes at every commit). `(Env)` is placed first whenever tooling or environment setup is a prerequisite:
`(Env) -> Wiring -> Contract -> Harness -> Logic -> Migration -> Refactor -> Cleanup`

**Format:**
- [ ] **Wiring** - Connect outermost boundaries with skeleton response.
- [ ] **Contract** - Define port interfaces and DTOs.
- [ ] **Logic** - Implement business logic replacing skeleton responses.

## Implementation Notes
Free-form notes recording decisions, deviations, or discoveries during implementation.

## Verification
Action-oriented black-box checks executed strictly from the outside as an end user would (e.g. CLI commands, flags, observable output, exit codes). All must pass before slice completion.

**Format:**
- [ ] Run `command <args>` and verify output contains `expected output` and exits with code 0.
- [ ] Run `command <invalid-args>` and verify error message and non-zero exit.
