# Slice: Refactor `ContextResult` to `ProjectContext`

- **Status:** Planned
- **Milestone:** [08-core-refactoring-and-enhancements](/docs/project/milestones/08-core-refactoring-and-enhancements.md)
- **Spec:** None

## 1. Business Goal & Interaction Sequence
**Goal:** To improve code clarity, maintainability, and type safety by replacing the legacy `ContextResult` data structure with a new, strictly-typed `ProjectContext` model. This refactoring aligns the codebase with modern Python practices (`@dataclass`) and is part of the broader initiative to modernize the system's core data transfer objects.

**Interaction:** This is a purely internal refactoring. There are no user-facing changes. The system's behavior when gathering project context will remain identical.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: New `ProjectContext` Model Exists
**Given** the system's source code
**When** a new file `src/teddy_executor/core/domain/models/project_context.py` is inspected
**Then** it should define a `ProjectContext` dataclass with `header` and `content` string attributes.

### Scenario 2: `IGetContextUseCase` Port is Updated
**Given** the inbound port for gathering context
**When** the file `src/teddy_executor/core/ports/inbound/get_context_use_case.py` is inspected
**Then** the `get_context` method signature in the `IGetContextUseCase` interface must return `ProjectContext`.

### Scenario 3: `ContextService` Implements the Updated Port
**Given** the primary service for context gathering
**When** the file `src/teddy_executor/core/services/context_service.py` is inspected
**Then** the `get_context` method in the `ContextService` class must return an instance of `ProjectContext`.

### Scenario 4: CLI Adapter is Updated
**Given** the main CLI entrypoint
**When** the file `src/teddy_executor/__main__.py` is inspected
**Then** the `context` command logic must be updated to handle the `ProjectContext` object and correctly print its content.

### Scenario 5: Legacy Model is Removed
**Given** the legacy models file
**When** `src/teddy_executor/core/domain/models/_legacy_models.py` is inspected
**Then** the `ContextResult` class definition should be completely removed.

### Scenario 6: All Tests Pass
**Given** the refactoring is complete
**When** the full test suite is run
**Then** all unit, integration, and acceptance tests must pass.

## 3. User Showcase

This is an internal refactoring with no user-facing changes. The success of the refactoring will be verified by the comprehensive test suite.

## 4. Architectural Changes

This refactoring replaces the legacy `ContextResult` class with a modern, `@dataclass`-based `ProjectContext` DTO. This change improves type safety and clarifies the data contract for project context results throughout the system.

The core architectural updates are:
1.  **New Data Contract:** A new `ProjectContext` component has been defined to serve as the strict data transfer object for project context.
2.  **Updated Port Contract:** The `IGetContextUseCase` inbound port has been updated. Its `get_context` method now returns the new `ProjectContext` type, enforcing the new contract at the architecture's boundary.
3.  **Updated Service Contract:** The `ContextService` now assembles and returns the `ProjectContext` DTO.

These changes are codified in the following design documents:

- **New Component:** [ProjectContext Design](/docs/architecture/core/domain/project_context.md)
- **Updated Component:** [IGetContextUseCase Port Design](/docs/architecture/core/ports/inbound/get_context_use_case.md)
- **Updated Component:** [ContextService Design](/docs/architecture/core/services/context_service.md)

## 5. Scope of Work

This refactoring will be executed using a safe "Create, Migrate, Delete" sequence to ensure a smooth transition from the old `ContextResult` class to the new `ProjectContext` `@dataclass`.

### 1. Create New `ProjectContext` Contract
-   **File:** `src/teddy_executor/core/domain/models/project_context.py` (new file)
    -   Create the new file.
    -   Add `from dataclasses import dataclass`.
    -   Define the `ProjectContext` dataclass as specified in the [component design document](/docs/architecture/core/domain/project_context.md).
-   **File:** `src/teddy_executor/core/domain/models/__init__.py`
    -   Import `ProjectContext` and add it to the `__all__` list.

### 2. Migrate Port, Service, Adapter, and Consumers
-   **File:** `src/teddy_executor/core/ports/inbound/get_context_use_case.py`
    -   Change the import from `ContextResult` to `ProjectContext`.
    -   Update the `get_context` method's return type hint to `ProjectContext`.
-   **File:** `src/teddy_executor/core/services/context_service.py`
    -   Update imports to use `ProjectContext`.
    -   Update the `get_context` method to assemble and return a `ProjectContext` instance. The formatting logic previously in `cli_formatter.py` should be moved here to construct the `header` and `content` strings.
-   **File:** `src/teddy_executor/adapters/inbound/cli_formatter.py`
    -   Update the `format_project_context` function to accept a `ProjectContext` object.
    -   Simplify the function to simply combine the `header` and `content` attributes into a single string.
-   **File:** `src/teddy_executor/__main__.py`
    -   In the `context` command, ensure the new `ProjectContext` object is correctly passed to the formatter.

### 3. Migrate Tests
-   **File:** `tests/unit/core/services/test_context_service.py`
    -   Update the tests to assert that the service returns a `ProjectContext` object with correctly formatted `header` and `content` strings.
-   **File:** `tests/unit/adapters/inbound/test_cli_formatter.py`
    -   Update the tests to verify the new, simplified formatting logic.
-   **File:** `tests/acceptance/test_generalized_clipboard_output.py`
    -   Update the mock for `context_service.get_context` to return a `ProjectContext` instance. Adjust assertions to match the new combined output format.

### 4. Delete Legacy `ContextResult`
-   **File:** `tests/unit/core/domain/test_models.py`
    -   Delete the test case for `ContextResult`.
-   **File:** `src/teddy_executor/core/domain/models/_legacy_models.py`
    -   Delete the entire `ContextResult` class definition.
-   **File:** `src/teddy_executor/core/domain/models/__init__.py`
    -   Remove `ContextResult` from the imports and the `__all__` list.

### 5. Verification
-   Run the entire test suite (`poetry run pytest`) to ensure all tests pass and the refactoring is complete and correct.
-   Run the pre-commit hooks (`poetry run pre-commit run --all-files`) to ensure type-checking and linting pass.
