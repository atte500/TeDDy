# Slice: Consistent Mismatch Indicators for Plan Parser

## Business Goal
Improve the developer experience when debugging malformed plans by providing a consistent and highly visible visual cue (` <-- MISMATCH`) for both top-level structural errors and internal `EDIT` action errors.

## Acceptance Criteria

### Scenario 1: Missing REPLACE block in EDIT action
Given a plan where an `EDIT` action has a `FIND:` heading and code block, but is missing the `REPLACE:` heading.
When the plan is parsed.
Then an `InvalidPlanError` should be raised with the message:
`Missing REPLACE block after FIND block <-- MISMATCH`

### Scenario 2: Consistent Top-Level Structural Errors
Given a plan with an invalid top-level structure (e.g., missing Rationale).
When the plan is parsed.
Then the error message must include the structural summary, and the mismatching line must end with exactly ` <-- MISMATCH` (using the same shared constant as Scenario 1).

## User Showcase
1. Create a file `malformed_plan.md` with an `EDIT` action that ends after a `FIND` code block.
2. Run `teddy execute malformed_plan.md`.
3. Verify the output contains the string ` <-- MISMATCH`.

## Architectural Changes

### `src/teddy_executor/core/services/parser_infrastructure.py`
- Define a constant `MISMATCH_INDICATOR = " <-- MISMATCH"`.

### `src/teddy_executor/core/services/markdown_plan_parser.py`
- Import `MISMATCH_INDICATOR`.
- Update `_format_structural_mismatch_msg` to use this constant instead of the hardcoded string.

### `src/teddy_executor/core/services/action_parser_strategies.py`
- Import `MISMATCH_INDICATOR`.
- Update `parse_find_replace_pair` to catch both missing `REPLACE:` heading and missing `REPLACE` code block.
- Raise `InvalidPlanError(f"Missing REPLACE block after FIND block{MISMATCH_INDICATOR}")` for both cases.

## Deliverables
- [x] Refactored `parser_infrastructure.py` with shared constant.
- [x] Updated `markdown_plan_parser.py` using the shared constant.
- [x] Updated `action_parser_strategies.py` with unified, indicator-aware `EDIT` error.
- [x] Unit or Integration test verifying the specific error message for missing `REPLACE` blocks.
