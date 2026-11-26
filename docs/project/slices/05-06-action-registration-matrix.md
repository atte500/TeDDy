# Slice: Action-Type Registration Matrix Test
- **Status:** Planned
- **Milestone:** [Milestone 5: Quality Gate & Debt Reconciliation](/docs/project/milestones/05-quality-gate-debt-reconciliation.md)
- **Depends On:** None
- **Specs:** [Plan Format](/docs/project/specs/plan-format.md), [Plan Format Validation](/docs/project/specs/plan-format-validation.md)
- **Prototype:** None
- **Component Docs:** [MarkdownPlanParser](/docs/architecture/core/services/markdown_plan_parser.md), [ActionFactory](/docs/architecture/core/services/action_factory.md), [PlanValidator](/docs/architecture/core/services/plan_validator.md), [MarkdownPlanBuilder](/docs/architecture/tests/drivers/plan_builder.md)
- **Scope Slug:** `action-registration-matrix`

## Goal
Prove that every action type the protocol declares survives the whole chain — parse, validate, create, render — so adding a type is a single visible edit rather than a six-site scavenger hunt that fails only when a user writes the new type in a plan.

## Context
- Registration surface, as built: `git grep "ActionType"` matches eight files — `core/domain/models/plan.py` (the enum), `core/domain/models/__init__.py` (re-export), `core/services/action_parser_complex.py`, `core/services/markdown_plan_parser.py`, `core/services/validation_rules/helpers.py`, `core/services/session_lifecycle_manager.py`, `core/services/session_service.py`, and `adapters/inbound/textual_plan_reviewer_helpers.py`. The milestone's "six sites" is a summary of these and must be re-derived at implementation rather than trusted.
- The failure mode this guards: a type missing from the parser dispatch map fails pre-flight with "Unknown action type", while a type missing from the renderer produces an unlabelled log entry — two different symptoms from one class of omission, neither caught by a test that only exercises the types already in use.
- Why it must land before [slice 04-11](./04-11-move-delete-actions.md): that slice adds `MOVE` and `DELETE`, which touch every one of those sites. A guard authored afterwards cannot catch the omission it was written for.
- Why it is temporary: [Milestone 6](/docs/project/milestones/06-cross-cutting-consolidation.md) collapses the registration sites into one declaration, after which the matrix is redundant by construction and must be deleted rather than maintained.
- Harness availability: `MarkdownPlanBuilder` already emits validated plans by action type, so the matrix can drive the public chain instead of asserting on private maps, which keeps the test honest about what a user would experience.
- Deliberately out of scope: the `MOVE`/`DELETE` contracts themselves, which are slice 04-11's; this slice only asserts that whatever the enum declares is fully registered.

## Scenarios

> As a maintainer, I want a new action type to fail the suite if I forget a registration site.

```gherkin
Given an action type declared on the ActionType enum
When the registration matrix runs
Then a builder-generated plan containing only that type parses without an unknown-type error
And the factory creates the matching action object
And the validator accepts or rejects it with a type-specific message rather than an unknown-type one
And the rendered report entry carries a label distinct from every sibling type
```

> As a maintainer, I want the matrix to cover the enum rather than a hand-written list.

```gherkin
Given a newly added ActionType member
When the matrix runs
Then it exercises that member without any edit to the test
Because the matrix derives its cases from the enum
```

> As a maintainer, I want a type-specific rejection to stay distinguishable from a missing registration.

```gherkin
Given a MOVE action with an occupied destination
When the matrix validates it
Then the failure names the destination
And it is not reported as an unknown action type
```

## Edge Cases
- **Terminal `MESSAGE` type**: If the matrix drives `MESSAGE` through validation, then the fixture must present it as a communicating turn, because validation treats a terminal action differently from an executable one.
- **Filesystem-touching validators**: If a type's validator requires an existing path (`READ`, `EDIT`), then the fixture seeds the path in the harness workspace, because a rejection for a missing file would mask a registration omission.
- **Network-touching types**: If a type would reach a remote service during creation, then the fixture injects the harness double, because the matrix must not perform I/O to prove a registration.
- **Renderer label uniqueness**: If two types render the same label, then the matrix fails, because an unlabelled log entry is precisely the symptom being guarded.
- **Parametrized fixtures returning a builder**: If the per-type fixture itself raises `StopIteration`, then pytest reports the case as an error rather than a failure, because a fixture must never silently skip a type.
- **Enum growth without a fixture**: If a member is added to the enum but not to the per-type parameter table, then the matrix fails with a named missing type, because the table is asserted complete against the enum rather than assumed.
- **Deprecated member**: If a member is later deprecated, then the matrix keeps exercising it until the enum drops it, because the protocol and the enum are the same contract.

## Key Unknowns
- [ ] [Technical] Registration reachability: are the parser dispatch map, both factory maps, and the validator registry queryable as plain mappings, or are they closures behind the public services? Design Sensitivity: if mapping-shaped → the matrix asserts each map directly and additionally drives one type end to end for confidence; if closure-shaped → the matrix drives every type through the public chain only, and the "site was edited" claim rests on observable behaviour rather than on introspection.

## Impact
1. `[NEW]` A parameterized registration matrix test in the unit tier, deriving its cases from `list(ActionType)` and asserting the table covers the enum.
2. `[NEW]` A per-type fixture bundle in the harness — a minimal valid parameter set and a deliberately invalid variant — so each type is driven through both the accepted and the rejected branch.
3. `[EXTEND]` `MarkdownPlanBuilder` — whatever builder support the matrix needs for types it cannot emit yet.
4. `[MIGRATE]` The `MarkdownPlanParser`, `ActionFactory`, and `PlanValidator` component pages — record that the matrix is the registration guard and that it becomes redundant when Milestone 6 collapses the sites.

## Deliverables
- [ ] **Harness** — Add the per-type fixture bundle and any missing `MarkdownPlanBuilder` support, asserting the bundle's key set equals the enum's member set.
- [ ] **Core** — Implement the matrix over the public chain with the accepted and rejected branch per type, and prove it catches a deliberately removed registration before the fix is restored.
- [ ] **Cleanup** — Record the guard's temporary status and its planned deletion on the three affected component pages.

## Implementation Notes

## Verification
1. **Guard bites:**
   Temporarily remove one type from the parser dispatch map on a scratch branch and run the matrix.
   Verify it fails naming the removed type.
2. **Coverage follows the enum:**
   Add a throwaway enum member without registering it and confirm the matrix fails on that member alone, then revert.
3. **No I/O leakage:**
   Run the matrix with the network and filesystem doubles asserting they saw only the calls the fixtures declared.
