# Refactor Legacy Domain DTOs

## 1. Goal (The "Why")

The goal of this initiative is to address the technical debt residing in `_legacy_models.py` by refactoring the core Data Transfer Objects (DTOs) that are still in active use. This effort will improve the **clarity, structure, and robustness** of our core domain models, making the codebase more maintainable and aligned with modern architectural standards.

This will be achieved by focusing on three key areas:

1.  **Improve Naming Clarity:** Rename models to better reflect the domain entities they represent, moving from implementation-focused names (e.g., `ContextResult`) to domain-focused names (e.g., `ProjectContext`).
2.  **Modernize Structure & Location:** Eliminate the architectural confusion caused by the `_legacy_models.py` file. Each refactored model will be moved into its own dedicated module within `src/teddy_executor/core/domain/models/`, following the project's established "one model, one file" convention.
3.  **Enhance Robustness & Documentation:** Refactor the underlying implementation of simple data containers to use `TypedDict` for improved static analysis, while retaining `dataclasses` for more complex entities. Add comprehensive docstrings to all models and their fields to improve developer ergonomics.

## 2. Proposed Solution (The "What")

The solution is to systematically replace the legacy DTOs with new, well-defined models, each in its own dedicated module. This will be an incremental process of creating the new model, updating the application to use it, and then removing the legacy version.

### Refactoring Plan

| Legacy Model    | New Name           | New File Path                         | Implementation Choice |
| --------------- | ------------------ | ------------------------------------- | --------------------- |
| `ContextResult` | `ProjectContext`   | `domain/models/project_context.py`    | `@dataclass`          |
| `CommandResult` | `ShellOutput`      | `domain/models/shell_output.py`       | `TypedDict`           |
| `SERPReport`    | `WebSearchResults` | `domain/models/web_search_results.py` | `TypedDict`           |
| `QueryResult`   | `QueryResult`      | (lives in `web_search_results.py`)    | `TypedDict`           |
| `SearchResult`  | `SearchResult`     | (lives in `web_search_results.py`)    | `TypedDict`           |

### Implementation Rationale

-   **`ProjectContext` (@dataclass):** As a core domain entity, a `@dataclass` is appropriate. It provides robust type-hinting and allows for the future addition of business logic (methods), which is not possible with `TypedDict`.
-   **`ShellOutput` (TypedDict):** This model is a simple, immutable container for data (`stdout`, `stderr`, `return_code`). `TypedDict` is the most lightweight, performant, and Pythonic choice for this kind of data structure, providing full static analysis support without class overhead.
-   **`WebSearchResults` (Nested TypedDicts):** This model represents a JSON-like data structure. A hierarchy of `TypedDict`s is the ideal way to model this, providing clarity and strong typing for a nested structure.

### Transition Strategy

The transition will be managed via the public API defined in `src/teddy_executor/core/domain/models/__init__.py`. The new models will be created and exported from the `__init__.py` file. Once all internal application code has been updated to use the new models, the old versions will be removed from `_legacy_models.py` and the `__init__.py` exports.

## 3. Implementation Analysis (The "How")

The refactoring will be executed as a series of "create, migrate, delete" steps for each legacy model, ensuring a safe and incremental transition.

1.  **Create:** A new file will be created for the new model (e.g., `project_context.py`) containing the improved `dataclass` or `TypedDict` definition.
2.  **Migrate:** All files that currently import the legacy model will be updated to import and use the new model. This includes updating type hints in ports, implementation logic in services and adapters, and assertions in tests.
3.  **Delete:** Once the migration is complete and all tests pass, the legacy model's definition will be removed from `_legacy_models.py` and its export will be removed from `models/__init__.py`.

The codebase audit has identified all impacted files, and the changes are well-distributed, making a sliced approach ideal for managing complexity.

## 4. Vertical Slices

This work is divided into three independent vertical slices, one for each core domain concept. They can be implemented in any order.

---
### **Slice 1: Refactor `CommandResult` to `ShellOutput`**
**Goal:** Replace the `CommandResult` dataclass with a `ShellOutput` TypedDict.
-   **[ ] Task: Create `shell_output.py`** with the new `ShellOutput` TypedDict.
-   **[ ] Task: Update Application Code:** `ports/outbound/shell_executor.py`, `adapters/outbound/shell_adapter.py`, `services/action_dispatcher.py`.
-   **[ ] Task: Update Tests:** `tests/unit/core/domain/test_models.py`.
-   **[ ] Task: Finalize & Cleanup:** Update `models/__init__.py` and remove `CommandResult` from `_legacy_models.py`.

---
### **Slice 2: Refactor `SERPReport` to `WebSearchResults`**
**Goal:** Replace the search-related dataclasses with a nested `WebSearchResults` TypedDict.
-   **[ ] Task: Create `web_search_results.py`** with the new `WebSearchResults`, `QueryResult`, and `SearchResult` TypedDicts.
-   **[ ] Task: Update Application Code:** `ports/outbound/web_searcher.py`, `adapters/outbound/web_searcher_adapter.py`.
-   **[ ] Task: Update Tests:** `tests/unit/core/domain/test_models.py`, `tests/integration/adapters/outbound/test_web_searcher_adapter.py`, `tests/acceptance/test_research_action.py`.
-   **[ ] Task: Finalize & Cleanup:** Update `models/__init__.py` and remove the old models from `_legacy_models.py`.

---
### **Slice 3: Refactor `ContextResult` to `ProjectContext`**
**Goal:** Replace the `ContextResult` dataclass with a more robust `ProjectContext` dataclass.
-   **[ ] Task: Create `project_context.py`** with the new `ProjectContext` dataclass.
-   **[ ] Task: Update Application Code:** `ports/inbound/get_context_use_case.py`, `services/context_service.py`, `adapters/inbound/cli_formatter.py`.
-   **[ ] Task: Update Tests:** `tests/unit/core/domain/test_models.py`, `tests/unit/core/services/test_context_service.py`, `tests/unit/adapters/inbound/test_cli_formatter.py`, `tests/acceptance/test_generalized_clipboard_output.py`.
-   **[ ] Task: Finalize & Cleanup:** Update `models/__init__.py` and remove `ContextResult` from `_legacy_models.py`.
