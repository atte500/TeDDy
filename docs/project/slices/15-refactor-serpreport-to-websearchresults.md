# Slice: Refactor `SERPReport` to `WebSearchResults`

- **Status:** Implemented
- **Milestone:** [08-core-refactoring-and-enhancements](/docs/project/milestones/08-core-refactoring-and-enhancements.md)
- **Spec:** None

## 1. Business Goal & Interaction Sequence
**Goal:** To improve code clarity, maintainability, and type safety by replacing the legacy `SERPReport` data structure with a new, strictly-typed `WebSearchResults` model. This refactoring aligns the codebase with modern Python practices (`TypedDict`) and is a key part of the broader initiative to modernize the system's core data transfer objects.

**Interaction:** This is a purely internal refactoring. There are no user-facing changes. The system's behavior when executing web searches will remain identical.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: New `WebSearchResults` Model Exists
**Given** the system's source code
**When** a new file `src/teddy_executor/core/domain/models/web_search_results.py` is inspected
**Then** it should define nested `TypedDict` models for `WebSearchResults` and individual `SearchResult` entries.

### Scenario 2: `IWebSearcher` Port is Updated
**Given** the outbound port for web searching
**When** the file `src/teddy_executor/core/ports/outbound/web_searcher.py` is inspected
**Then** the `search` method signature in the `IWebSearcher` interface must return `WebSearchResults`.

### Scenario 3: `WebSearcherAdapter` Implements the Updated Port
**Given** the primary adapter for web searching
**When** the file `src/teddy_executor/adapters/outbound/web_searcher_adapter.py` is inspected
**Then** the `search` method in the `WebSearcherAdapter` class must return an instance of `WebSearchResults`.

### Scenario 4: Legacy Model is Removed
**Given** the legacy models file
**When** `src/teddy_executor/core/domain/models/_legacy_models.py` is inspected
**Then** the `SERPReport` class definition should be completely removed.

### Scenario 5: All Dependent Services are Updated
**Given** any service that consumes the output of a web search
**When** the codebase is inspected
**Then** all previous references to `SERPReport` must be replaced with `WebSearchResults`, and attribute access must be updated to dictionary access.

### Scenario 6: All Tests Pass
**Given** the refactoring is complete
**When** the full test suite is run
**Then** all unit, integration, and acceptance tests must pass.

## 3. User Showcase

This is an internal refactoring with no user-facing changes. The success of the refactoring will be verified by the comprehensive test suite.

## 4. Architectural Changes

This refactoring replaces the legacy `SERPReport` class with a modern, `TypedDict`-based `WebSearchResults` DTO. This change improves type safety and clarifies the data contract for web search results throughout the system.

The core architectural updates are:
1.  **New Data Contract:** A new `WebSearchResults` component has been defined to serve as the strict data transfer object for web search results.
2.  **Updated Port Contract:** The `IWebSearcher` outbound port has been updated. Its `search` method now returns the new `WebSearchResults` type, enforcing the new contract at the architecture's boundary.

These changes are codified in the following design documents:

- **New Component:** [WebSearchResults Design](/docs/architecture/core/domain/web_search_results.md)
- **Updated Component:** [IWebSearcher Port Design](/docs/architecture/core/ports/outbound/web_searcher.md)

## 5. Scope of Work

This refactoring will be executed using a safe "Create, Migrate, Delete" sequence to ensure a smooth transition from the old `SERPReport` class to the new `WebSearchResults` `TypedDict`.

### 1. Create New `WebSearchResults` Contract
-   **File:** `src/teddy_executor/core/domain/models/web_search_results.py` (new file)
    -   Create the new file.
    -   Add `from typing import TypedDict, List`.
    -   Define the `SearchResult` and `WebSearchResults` TypedDicts as specified in the [component design document](/docs/architecture/core/domain/web_search_results.md).

### 2. Migrate Port, Adapter, and Consumers
-   **File:** `src/teddy_executor/core/ports/outbound/web_searcher.py`
    -   Change the import from `SERPReport` to `from teddy_executor.core.domain.models.web_search_results import WebSearchResults`.
    -   Update the `search` method's return type hint to `WebSearchResults`.
-   **File:** `src/teddy_executor/adapters/outbound/web_searcher_adapter.py`
    -   Update the import to use `WebSearchResults`.
    -   Change the `search` method's return type hint to `WebSearchResults`.
    -   Update the implementation to construct and return a `WebSearchResults` dictionary instead of a `SERPReport` object.
-   **File:** `src/teddy_executor/core/services/action_dispatcher.py`
    -   Update the imports to use `WebSearchResults` instead of `SERPReport`.
    -   In `_format_results`, update the logic to handle the `WebSearchResults` dictionary.

### 3. Migrate Tests
-   **File:** `tests/integration/adapters/outbound/test_web_searcher_adapter.py`
    -   Update the test to assert the new `WebSearchResults` dictionary structure instead of the `SERPReport` object instance.
-   **File:** `tests/acceptance/test_research_action.py`
    -   This test relies on a mocked `SERPReport`. Update the mock to return a `WebSearchResults` dictionary and update assertions accordingly.

### 4. Delete Legacy `SERPReport`
-   **File:** `tests/unit/core/domain/test_models.py`
    -   Delete the `test_serp_report_instantiation` test case, as `TypedDict` does not require instantiation tests.
-   **File:** `src/teddy_executor/core/domain/models/_legacy_models.py`
    -   Delete the entire `SERPReport`, `QueryResult`, and `SearchResult` class definitions.
-   **File:** `src/teddy_executor/core/domain/models/__init__.py`
    -   Remove `SERPReport`, `QueryResult`, and `SearchResult` from the imports and the `__all__` list.

### 5. Verification
-   Run the entire test suite (`poetry run pytest`) to ensure all tests pass and the refactoring is complete and correct.

## Implementation Summary

This refactoring was executed successfully following a "Create, Migrate, Delete" strategy, driven by a series of small TDD cycles.

1.  **Create:** A new `WebSearchResults` `TypedDict` model was created in `src/teddy_executor/core/domain/models/web_search_results.py`, driven by a new unit test.
2.  **Migrate:**
    *   The `IWebSearcher` port and `WebSearcherAdapter` were updated to return the new `WebSearchResults` dictionary. This change was driven by an integration test.
    *   The `MarkdownReportFormatter`'s Jinja2 template was updated to correctly render the new dictionary structure. This was driven by a failing acceptance test, which was then resolved via a new unit test for the formatter.
3.  **Delete:** The legacy `SERPReport`, `QueryResult`, and `SearchResult` dataclasses were removed from `_legacy_models.py`, along with their associated unit tests. The final references were cleaned up from the `models/__init__.py` file.

The entire refactoring was completed without changing any user-facing behavior, and the full test suite remained green at the end of the process. A minor `mypy` type-checking issue was caught and fixed during the pre-commit stage.

### Refactoring Opportunities
- None.
