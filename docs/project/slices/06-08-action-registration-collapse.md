# Slice: Collapse the Action-Type Registration Surface
- **Status:** Planned
- **Milestone:** [Milestone 6: Cross-Cutting Consolidation](/docs/project/milestones/06-cross-cutting-consolidation.md)
- **Depends On:** [04-11-move-delete-actions](./04-11-move-delete-actions.md), [05-06-action-registration-matrix](./05-06-action-registration-matrix.md)
- **Specs:** [Plan Format](/docs/project/specs/plan-format.md), [Plan Format Validation](/docs/project/specs/plan-format-validation.md)
- **Prototype:** None
- **Component Docs:** [MarkdownPlanParser](/docs/architecture/core/services/markdown_plan_parser.md), [ActionFactory](/docs/architecture/core/services/action_factory.md), [PlanValidator](/docs/architecture/core/services/plan_validator.md), [MarkdownPlanBuilder](/docs/architecture/tests/drivers/plan_builder.md)
- **Scope Slug:** `action-registration-collapse`

## Goal
Declare each action type once — enum member, protocol name, parser strategy, factory construction, validator rules, and report label — so adding a type is a single visible edit that no second site can contradict, and retire the matrix test that exists only to police the duplication.

## Context
- Surface as built: `git grep "ActionType"` matches eight files — `core/domain/models/plan.py` (the enum), `core/domain/models/__init__.py` (re-export), `core/services/action_parser_complex.py`, `core/services/markdown_plan_parser.py`, `core/services/validation_rules/helpers.py`, `core/services/session_lifecycle_manager.py`, `core/services/session_service.py`, and `adapters/inbound/textual_plan_reviewer_helpers.py`. Milestone 05's "six registration sites" is a summary of these and is re-derived during the migration rather than trusted.
- Three distinct failure modes from one class of omission: a type missing from the parser dispatch fails pre-flight with "Unknown action type"; missing from a factory map raises only when a user writes that type; missing from the renderer produces an unlabelled log entry that no test notices.
- Ordering against 04-11: MOVE and DELETE edit every one of those sites, so collapsing first would mean performing the collapse twice.
- Ordering against 05-06: the registration matrix is the behavioural-equivalence proof this migration runs against. It is deleted at the end of this slice, never before, because deleting the guard first would make a silent divergence indistinguishable from a clean migration.
- Boundary: the declaration lives in `core/domain/models/` and must not import an adapter. Per-type construction that needs a port is expressed as a callable resolved through the existing `ActionPorts` DTO, because the composition root builds ports and core resolves none.
- Two core consumers bind by protocol name string rather than by enum member (`session_service.py`, `session_lifecycle_manager.py`), so the declaration has to serve name-keyed lookup as well as enum-keyed registration.
- Renderer coupling: `execution_report.md.j2` currently decides the label from the action name, which makes the template a seventh registration site. The declaration supplies the label and the template renders it.
- What must not change: the Markdown action names in the protocol, every rendered label, and the pre-flight error text for an unknown type.

## Scenarios

> As a maintainer, I want adding an action type to be one edit.

```gherkin
Given a new member declared in the single registration declaration
When a plan containing only that type is parsed, validated, created, and rendered
Then all four succeed
And no other module required an edit
```

> As a maintainer, I want an incomplete declaration to fail at import rather than at a user's plan.

```gherkin
Given a member declared on the enum with no binding
When the registry is built
Then a TeddyError subclass names the member
And the failure is not an "Unknown action type" pre-flight message
```

> As a maintainer, I want the temporary guard retired only after it proves equivalence.

```gherkin
Given the collapse has landed
When the migration is complete
Then 05-06's registration matrix produces the same results it produced before the collapse
And it is deleted together with its harness fixture bundle
```

## Edge Cases
- **Port-needing construction**: If a type's factory requires a filesystem or shell port, then the binding holds a callable taking `ActionPorts`, because an eagerly built instance would move port resolution into core.
- **Terminal `MESSAGE`**: If validation treats a terminal action differently, then the binding declares terminality rather than the validator testing the name, because a name test is the second site being removed.
- **Multiple validator rules**: If one type maps to several rules today, then the binding holds an ordered list, because collapsing to one silently drops a check.
- **Template condition**: If the report template switches on the action name, then it renders the declared label, because a template branch is a registration site that no hook can see.
- **Name-keyed consumer**: If a core service looks up by protocol name, then the registry exposes that lookup, because converting those callers to enum lookup is a behaviour change outside this slice.
- **Removed member**: If a member leaves the enum while its binding survives, then the registry fails to build, because an orphaned binding compiles and is never exercised.
- **Import cycle**: If a parser strategy needs the registry, then the strategy registers itself against the declaration and does not import the registry, because the registry has to stay the leaf of that graph.

## Key Unknowns
- [ ] [Technical] Whether the factory maps and validator registry are plain mappings that can be replaced by one declaration, or are closures interleaved with service construction. Design Sensitivity: if plain mappings → the collapse is a data move plus four call-site rewrites and lands in one commit; if closures → the declaration holds per-type callables resolved through `ActionPorts`, 05-06's matrix carries the equivalence proof across two commits, and the slice splits into a declaration step and a migration step.

## Impact
1. `[NEW]` The single action-type declaration in `core/domain/models/` — enum member → protocol name → parser strategy → factory callable → validator rules → report label.
2. `[MIGRATE]` `MarkdownPlanParser` and `action_parser_complex.py` — dispatch reads the declaration.
3. `[MIGRATE]` `ActionFactory` and both of its maps — construction reads the declaration.
4. `[MIGRATE]` `registries/validators.py` — validator lookup reads the declaration.
5. `[MIGRATE]` `execution_report.md.j2` — renders the declared label instead of branching on the name.
6. `[PRUNE]` 05-06's registration matrix test, its per-type fixture bundle, and the three component-page notes that call it temporary.
7. `[MIGRATE]` The four component pages above plus `docs/architecture/ARCHITECTURE.md` — record the declaration as the single registration site and drop the six-site description.

## Deliverables
- [ ] **Interface** — Land the declaration with its invariants documented, plus the `TeddyError` subclass raised when a member has no binding.
- [ ] **Harness** — Keep 05-06's matrix green through the migration and add the import-time completeness case.
- [ ] **Core** — Point the parser dispatch, both factory maps, and the validator lookup at the declaration.
- [ ] **Adapter** — Point the report template at the declared label.
- [ ] **Cleanup** — Delete the matrix, its fixtures, and the temporary-status notes; record the declaration on the four pages and in `ARCHITECTURE.md`.

## Implementation Notes

## Verification
1. **Single site:**
   Run `git grep -n "ActionType\." -- src`.
   Verify the only hits are the declaration module and legitimate enum-typed parameters.
2. **Completeness bites:**
   Add an enum member with no binding and import the registry.
   Verify a `TeddyError` subclass names it rather than an unknown-type pre-flight message.
3. **Equivalence:**
   Run 05-06's matrix immediately before and after the migration, then delete it.
   Verify both runs report identical per-type results.
