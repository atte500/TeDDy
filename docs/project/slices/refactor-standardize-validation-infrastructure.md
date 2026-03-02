# Refactor Slice: Standardize Validation Infrastructure

## 1. Business Goal
**Source Milestone:** [08-core-refactoring-and-enhancements](/docs/project/milestones/08-core-refactoring-and-enhancements.md)

This slice addresses technical debt identified during the test pyramid inversion (Slice 20). By standardizing how validation rules receive their dependencies (like `IFileSystemManager`), we improve the modularity and testability of the `PlanValidator`. This ensures that as the system grows, adding new validation rules remains simple and doesn't clutter the main validator service.

## 2. Acceptance Criteria (Scenarios)

### Scenario: Validation rules use constructor-based DI
- **Given** the `PlanValidator` service
- **When** it initializes its validation rules
- **Then** each rule (e.g., `CreateActionValidator`) receives its required outbound ports (like `IFileSystemManager`) via its constructor.
- **And** the `PlanValidator.validate()` method no longer passes these dependencies as arguments to validation functions.

### Scenario: Existing validation logic is preserved
- **Given** a plan with valid and invalid actions
- **When** the `PlanValidator` is executed
- **Then** all existing validation checks (safe paths, file existence, `EDIT` match checks) continue to function exactly as before.
- **And** the test suite (especially `tests/unit/core/services/test_plan_validator.py`) passes with 100% success.

## 3. Technical Specifications
- **Refactor Pattern:** Transition from functional rules in `src/teddy_executor/core/services/validation_rules/` to a Class-based or Protocol-based strategy pattern.
- **Dependency Management:** The `PlanValidator` constructor will continue to receive `IFileSystemManager`, which it will then inject into the individual rule objects.

## 4. Scope of Work
- [ ] Create `IActionValidator` protocol or base class.
- [ ] Refactor `create.py`, `edit.py`, `execute.py`, and `read.py` rules into classes implementing `IActionValidator`.
- [ ] Update `PlanValidator` to maintain a registry/list of these validator objects.
- [ ] Update `PlanValidator.validate` to iterate through the registry and delegate validation.
- [ ] Verify that all unit and integration tests for validation pass.
