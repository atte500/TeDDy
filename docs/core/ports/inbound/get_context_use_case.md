# Inbound Port: `IGetContextUseCase`

**Status:** Implemented
**Introduced in:** [Slice 13: Implement `context` Command](../../slices/13-context-command.md)

## 1. Responsibility

The `IGetContextUseCase` port defines the primary entry point into the application's core logic for gathering project context. It orchestrates the collection of various pieces of information about the project environment and returns them in a structured format.

## 2. Methods

### `get_context`
**Status:** Implemented

*   **Description:** Gathers all project context information, including the repository file tree, system environment details, and the content of specified files.
*   **Signature:** `get_context() -> ContextResult`
*   **Preconditions:** None.
*   **Postconditions:**
    *   Returns a `ContextResult` domain object containing the aggregated project context.

## 3. Related Spikes

*   N/A
