# Component Design: ReviewerContextScenarios
- **Status:** Implemented
- **Classification:** Test Setup
- **Source:** [`tests/harness/setup/reviewer_context_scenarios.py`](/tests/harness/setup/reviewer_context_scenarios.py)

## Purpose
A data-only module of canonical context-panel shapes plus the one plan the reviewer navigation scenarios drive. Each shape exists to make one panel branch reachable — every group, no History group, no panel at all — so a scenario selects a shape instead of hand-building a `ProjectContext`.

## Consumers
- [`TuiDriver`](../drivers/tui_driver.md): Receives the shape as `project_context` and the plan as `plan`.
- `tests/suites/unit/test_reviewer_context_scenarios_harness.py`: Asserts each shape through the same history predicate the panel builder consults.
- `tests/suites/unit/test_tui_driver.py`, `tests/suites/unit/adapters/inbound/test_section_navigation.py`, `tests/suites/acceptance/test_tui_section_boundaries.py`: Drive their scenarios from the canonical shapes and the canonical plan.

## Dependencies
- **`is_session_history_path`** (`teddy_executor.core.utils.markdown`): The predicate the panel uses to hoist a session's own turn records into History. The shapes are built so this predicate, not a hand-written label, decides what each shape means.
- **`ContextItem`, `ProjectContext`, `Plan`, `ActionData`**: The domain DTOs the shapes are expressed in.

## Class Invariants
- `paths_decide_the_shape`: Every shape is built from real session paths under `SESSION_ROOT`, so the panel's own predicates classify them and a shape cannot silently stop meaning what its name says.
- `populated_owns_every_group`: `populated` carries Session and Turn items plus this session's own turn records, so all four group headers render.
- `history_less_carries_no_history`: `history_less` carries Session and Turn items only, so no History group renders.
- `none_renders_no_panel`: `none` returns `None`, which is how the reviewer builds no Context root at all.
- `plan_carries_a_recognized_heading`: `reviewer_plan` writes a `### Summary` rationale, so the reviewer builds a Rationale root beside the Action Plan.

## Inbound Ports
- **`reviewer_project_context(shape)`**: Returns the `ProjectContext` for `populated` or `history_less`, and `None` for `none`.
- **`reviewer_plan(action_count=1)`**: Returns the `### Summary` plan the navigation scenarios drive.
- **Constants**: `SESSION_ROOT`, `SESSION_ITEM_PATH`, `TURN_ITEM_PATH`, `HISTORY_PLAN_PATH`, `HISTORY_REPORT_PATH`, `READ_RESOURCE`, and the `ReviewerContextShape` literal, so a test asserts against the same paths the shapes use instead of restating them.

## Outbound Ports
None — data-only module.

## Data Contracts
- **`ReviewerContextShape`**: `Literal["populated", "history_less", "none"]`, the closed set of panel shapes.
- **`ContextItem`**, **`ProjectContext`**, **`Plan`**, **`ActionData`**: The DTOs the builders return.

## Operations

### `reviewer_project_context(shape) -> Optional[ProjectContext]`
- **Preconditions:** `shape` is one of the three literals.
- **Postconditions:** `none` returns `None`; `history_less` returns a DTO with one Session and one Turn item; `populated` adds two of this session's own turn records, which the panel hoists into History and excludes from the scope groups.

### `reviewer_plan(action_count=1) -> Plan`
- **Preconditions:** `action_count` is a positive count. No guard enforces it, because the plan is only ever built from literal test constants.
- **Postconditions:** Returns a plan with a `### Summary` rationale and `action_count` READ actions. The count is what lets a boundary scenario overflow the tree viewport, which one action never does.
