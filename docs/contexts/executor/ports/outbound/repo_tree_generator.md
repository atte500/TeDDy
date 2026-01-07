# Outbound Port: `IRepoTreeGenerator`

**Status:** Implemented
**Introduced in:** [Slice 13: Implement `context` Command](../../slices/13-context-command.md)

## 1. Responsibility

The `IRepoTreeGenerator` port defines a technology-agnostic interface for generating a string representation of a repository's file and directory tree. A key responsibility is that the generated tree must respect the ignore patterns found in a `.gitignore` file.

## 2. Methods

### `generate_tree`
**Status:** Implemented

*   **Description:** Generates a multi-line string representing the file tree of the project.
*   **Signature:** `generate_tree() -> str`
*   **Preconditions:** None.
*   **Postconditions:**
    *   Returns a string formatted as a hierarchical tree.
    *   The returned tree must not include files or directories that match patterns in the project's `.gitignore` file.

## 3. Related Spikes

*   N/A - However, the implementation is based on the findings from the RCA documented in [`docs/rca/unreliable-third-party-library-gitwalk.md`](../../rca/unreliable-third-party-library-gitwalk.md).
