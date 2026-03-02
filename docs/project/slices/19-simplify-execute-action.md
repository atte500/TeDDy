# Slice 19: Simplify `EXECUTE` Action Syntax

## 1. Business Goal
To simplify the `EXECUTE` action by enforcing a "one command per action" rule. This will improve the user's control over plan execution, provide more precise fault isolation, and reduce the architectural complexity of the `ShellAdapter`.

## 2. Acceptance Criteria

**Scenario: Valid single-line `EXECUTE` action passes validation**
- **GIVEN** a plan with an `EXECUTE` action containing a single shell command
- **WHEN** the plan is validated by `teddy execute`
- **THEN** validation succeeds and execution proceeds.

**Scenario: Plan with multi-line `EXECUTE` action fails validation**
- **GIVEN** a plan with an `EXECUTE` action containing multiple command lines
- **WHEN** the plan is validated
- **THEN** validation fails with a clear error message indicating that only one command is allowed.

**Scenario: Plan with `&&` in `EXECUTE` action fails validation**
- **GIVEN** a plan with an `EXECUTE` action containing `&&` to chain commands
- **WHEN** the plan is validated
- **THEN** validation fails with a clear error message indicating that command chaining is not allowed.

**Scenario: Execution environments are isolated between actions**
- **GIVEN** a plan with two sequential `EXECUTE` actions
- **AND** the first action contains a `cd src` directive
- **WHEN** the plan is executed
- **THEN** the second action's current working directory is the project root, not `src`.

## 3. Architectural Changes
- **`PlanValidator`**: Will be modified to include new validation logic specifically for `EXECUTE` actions.
- **`ShellAdapter`**: Will be simplified to remove all logic related to multi-command script decomposition.
- **Tests**: Unit and integration tests for `PlanValidator` and `ShellAdapter` will be updated to reflect these changes.

## 4. Scope of Work

1.  **Modify `PlanValidator` (`src/teddy_executor/core/services/plan_validator.py`)**
    -   Add a new validation method `_validate_execute_action(self, action: ActionData) -> List[ValidationError]`.
    -   This method should retrieve the command script from `action.params`.
    -   Iterate through the script lines to separate header directives (`cd ...`, `export ...`) from the executable command lines.
    -   Assert that there is **exactly one** executable command line remaining.
    -   Assert that this command line **does not** contain `&&`.
    -   If either assertion fails, return a `ValidationError` with a clear message.

2.  **Update `PlanValidator` Tests (`tests/unit/core/services/test_plan_validator.py`)**
    -   Add a new test `test_validate_execute_action_succeeds_for_single_command` to verify a valid plan passes.
    -   Add a new test `test_validate_execute_action_fails_for_multiline_commands` to verify a plan with multiple command lines is rejected.
    -   Add a new test `test_validate_execute_action_fails_for_chained_commands` to verify a plan with `&&` is rejected.

3.  **Simplify `ShellAdapter` (`src/teddy_executor/adapters/outbound/shell_adapter.py`)**
    -   Delete the `_decompose_command` method entirely.
    -   Refactor the `execute` method:
        -   Remove the `for cmd in self._decompose_command(command):` loop.
        -   The method should now process the incoming `command` string as a whole.
        -   Split the `command` string into lines. Separate the header directive lines from the single executable command line.
        -   Process all directive lines first to configure `current_cwd` and `current_env`.
        -   Execute the single remaining command line.
        -   Return the `ShellOutput` directly without accumulating output in `total_stdout` / `total_stderr`.

4.  **Update `ShellAdapter` Tests (`tests/integration/adapters/outbound/test_shell_adapter.py`)**
    -   Delete the following obsolete tests:
        -   `test_execute_halts_on_multiline_failure`
        -   `test_execute_halts_on_ampersand_chain_failure`
    -   Verify that all remaining tests still pass, as they correctly cover the behavior of executing a single command.

## Implementation Notes
Upon investigation, it was determined that the core requirements of this slice were already implemented in the existing codebase:
- The `PlanValidator` already enforces a "one command per action" rule for `EXECUTE` actions, correctly rejecting plans with multi-line scripts or `&&` chaining.
- The `ShellAdapter` is already simplified and correctly handles the execution of single commands.
- The validation logic is already covered by unit tests in `tests/unit/core/services/test_plan_validator.py`.

The work in this slice was therefore limited to adding acceptance tests to verify and document this pre-existing behavior. No changes to the source code were necessary.
