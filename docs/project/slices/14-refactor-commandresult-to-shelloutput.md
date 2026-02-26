# Slice: Refactor `CommandResult` to `ShellOutput`

- **Status:** Planned
- **Milestone:** [08-core-refactoring-and-enhancements](/docs/project/milestones/08-core-refactoring-and-enhancements.md)
- **Spec:** None

## 1. Business Goal & Interaction Sequence
**Goal:** To improve code clarity, maintainability, and type safety by replacing the legacy `CommandResult` data structure with a new, strictly-typed `ShellOutput` model. This refactoring aligns the codebase with modern Python practices (`TypedDict`) and is a key part of the broader initiative to modernize the system's core data transfer objects.

**Interaction:** This is a purely internal refactoring. There are no user-facing changes. The system's behavior when executing shell commands will remain identical.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: New `ShellOutput` Model Exists
**Given** the system's source code
**When** the `src/teddy_executor/core/domain/models/` directory is inspected
**Then** a new file `shell_output.py` should exist
**And** it should define a `TypedDict` named `ShellOutput` with `stdout`, `stderr`, and `return_code` keys.

### Scenario 2: `IShellExecutor` Port is Updated
**Given** the outbound port for shell execution
**When** the file `src/teddy_executor/core/ports/outbound/shell_executor.py` is inspected
**Then** the `execute` method signature in the `IShellExecutor` interface must return `ShellOutput`.

### Scenario 3: `ShellAdapter` Implements the Updated Port
**Given** the primary adapter for shell execution
**When** the file `src/teddy_executor/adapters/outbound/shell_adapter.py` is inspected
**Then** the `execute` method in the `ShellAdapter` class must return an instance of `ShellOutput`.

### Scenario 4: Legacy Model is Removed
**Given** the legacy models file
**When** `src/teddy_executor/core/domain/models/_legacy_models.py` is inspected
**Then** the `CommandResult` class definition should be completely removed.

### Scenario 5: All Dependent Services are Updated
**Given** any service that consumes the output of a shell command
**When** the codebase is inspected
**Then** all previous references to `CommandResult` (e.g., in `ExecutionOrchestrator`) must be replaced with `ShellOutput`, and attribute access (`.`) must be updated to dictionary access (`[]`).

### Scenario 6: All Tests Pass
**Given** the refactoring is complete
**When** the full test suite is run
**Then** all unit, integration, and acceptance tests must pass.

## 3. User Showcase

This is an internal refactoring with no user-facing changes. The success of the refactoring will be verified by the comprehensive test suite.

## 4. Architectural Changes

This refactoring replaces the legacy `CommandResult` class with a modern, `TypedDict`-based `ShellOutput` DTO. This change improves type safety and clarifies the data contract for shell command execution throughout the system.

The core architectural updates are:
1.  **New Data Contract:** A new `ShellOutput` component has been defined to serve as the strict data transfer object for shell execution results.
2.  **Updated Port Contract:** The `IShellExecutor` outbound port has been updated. Its `execute` method now returns the new `ShellOutput` type, enforcing the new contract at the architecture's boundary.

These changes are codified in the following design documents:

- **New Component:** [ShellOutput Design](/docs/architecture/core/domain/shell_output.md)
- **Updated Component:** [IShellExecutor Port Design](/docs/architecture/core/ports/outbound/shell_executor.md)

## 5. Scope of Work

This refactoring will be executed using a safe "Create, Migrate, Delete" sequence to ensure a smooth transition from the old `CommandResult` class to the new `ShellOutput` `TypedDict`.

### 1. Create New `ShellOutput` Contract
-   **File:** `src/teddy_executor/core/domain/models/shell_output.py` (new file)
    -   Create the new file.
    -   Add `from typing import TypedDict`.
    -   Define the `ShellOutput` TypedDict as specified in the [component design document](/docs/architecture/core/domain/shell_output.md).

### 2. Migrate Port, Adapter, and Consumers
-   **File:** `src/teddy_executor/core/ports/outbound/shell_executor.py`
    -   Change the import from `CommandResult` to `from teddy_executor.core.domain.models.shell_output import ShellOutput`.
    -   Update the `execute` method's return type hint to `ShellOutput`.
-   **File:** `src/teddy_executor/adapters/outbound/shell_adapter.py`
    -   Update the import to use `ShellOutput`.
    -   Change the `execute` method's return type hint to `ShellOutput`.
    -   Replace `return CommandResult(...)` with `return {"stdout": ..., "stderr": ..., "return_code": ...}` to return a valid `ShellOutput` dictionary.
-   **File:** `src/teddy_executor/core/services/action_dispatcher.py`
    -   Update the imports to use `ShellOutput` instead of `CommandResult`.
    -   In `_execute_action`, change the type check from `isinstance(execution_result, CommandResult)` to a check that confirms the result is a dictionary with the expected `ShellOutput` keys (e.g., `'stdout' in execution_result`).
    -   Update the `_format_results` method to handle the `ShellOutput` dictionary instead of the `CommandResult` object (i.e., use `result["stdout"]` instead of `result.stdout`).

### 3. Delete Legacy `CommandResult`
-   **File:** `tests/unit/core/domain/test_models.py`
    -   Delete the `test_command_result_instantiation` test case, as `TypedDict` does not require instantiation tests.
-   **File:** `src/teddy_executor/core/domain/models/_legacy_models.py`
    -   Delete the entire `CommandResult` class definition.
-   **File:** `src/teddy_executor/core/domain/models/__init__.py`
    -   Remove `CommandResult` from the imports and the `__all__` list.

### 4. Update Documentation & Verify
-   **File:** `docs/architecture/adapters/outbound/shell_adapter.md`
    -   Update the document to reflect that the adapter now returns a `ShellOutput` dictionary, not a `CommandResult` object.
-   **Verification:**
    -   Run the entire test suite (`poetry run pytest`) to ensure all tests pass and the refactoring is complete.
