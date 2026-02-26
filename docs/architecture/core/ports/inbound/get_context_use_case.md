# Inbound Port: `IGetContextUseCase`

**Status:** Implemented
**Introduced in:**
- [Slice 13: Implement `context` Command](../../slices/executor/13-context-command.md)
- [Slice 17: Refactor `context` Command Output](../../slices/executor/17-refactor-context-command-output.md)

## 1. Responsibility

The `IGetContextUseCase` port defines the primary entry point into the application's core logic for gathering project context. It orchestrates the collection of various pieces of information about the project environment and returns them in a structured format.

## 2. Methods

### `get_context`
**Status:** Implemented

*   **Description:** Gathers all project context information, including the repository file tree, system environment details, and the content of specified files.
*   **Signature:** `get_context() -> ProjectContext`
*   **Preconditions:** None.
*   **Postconditions:**
    *   Returns a `ProjectContext` data transfer object containing the aggregated project context, structured for standardized output.
    *   If `.teddy/project.context` does not exist, it will be created with default content before the context is gathered.

## 3. Data Structures

### `ProjectContext`
This is a data transfer object (DTO) that aggregates all the information gathered by the use case. For its detailed structure, see the [ProjectContext component design](/docs/architecture/core/domain/project_context.md).
