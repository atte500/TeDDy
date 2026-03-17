# Slice: Redundant Edit Validation Hints
- **Status:** Planned
- **Milestone:** [09-interactive-session-and-config](../milestones/09-interactive-session-and-config.md)
- **Specs:** [plan-format-validation](../specs/plan-format-validation.md)

## 1. Business Goal
Improve the UX of the `EDIT` action by providing actionable hints when an edit is redundant or potentially already applied. This reduces user confusion during manual retries or when an AI generates no-op plans.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Identical FIND and REPLACE Blocks [✓]
**Given** a plan contains an `EDIT` action where the `FIND` block and `REPLACE` block are string-identical
**When** the plan is validated
**Then** a `ValidationError` must be returned
**And** the error message must include: "**Hint:** FIND and REPLACE blocks are identical. This edit can be safely omitted."

#### Deliverables
- [✓] Update `src/teddy_executor/core/services/validation_rules/edit.py` to use the new hint for identical blocks.
- [✓] Add a unit test in `tests/unit/core/services/test_validator_edit.py` for this scenario.

#### Implementation Notes
- Enhanced `EditActionValidator` to detect identical FIND/REPLACE blocks and append the specific hint.
- Updated `InvalidPlanError` to carry a list of `validation_errors`.
- Refactored `teddy execute` command in `src/teddy_executor/__main__.py` to use `handle_validation_failure` for rich reporting of validation errors, ensuring hints are surfaced to the user.
- Added acceptance test `tests/acceptance/test_redundant_edit_hints.py` to verify the end-to-end reporting.

### Scenario 2: Already Applied Edit Detection
**Given** a plan contains an `EDIT` action where the `FIND` block is NOT found (score < threshold)
**And** the `REPLACE` block IS found (score >= threshold)
**When** the plan is validated
**Then** the `ValidationError` for the missing `FIND` block must be returned
**And** the error message must include: "**Hint:** The FIND block was not found, but the REPLACE block is already present. This change might have already been applied."

#### Deliverables
- [ ] Update `src/teddy_executor/core/services/validation_rules/edit.py` to perform the "Already Applied" check using `find_best_match_and_diff` if the initial FIND fails.
- [ ] Add a unit test in `tests/unit/core/services/test_validator_edit.py` verifying the presence of the hint.

## 3. Architectural Changes
- No structural changes; logic is encapsulated within `EditActionValidator._validate_single_edit`.
