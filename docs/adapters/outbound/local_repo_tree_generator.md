# Outbound Adapter: `LocalRepoTreeGenerator`

**Status:** Implemented
**Language:** Python 3.9+
**Introduced in:** [Slice 13: Implement `context` Command](../../slices/13-context-command.md)

## 1. Purpose

The `LocalRepoTreeGenerator` is an adapter that implements the `IRepoTreeGenerator` port. It interacts with the local file system to generate a file tree, using the `pathspec` library to correctly parse `.gitignore` files and exclude specified paths. Its logic is based on the verified solution from an earlier Root Cause Analysis.

## 2. Implemented Outbound Port

*   [`IRepoTreeGenerator`](../../core/ports/outbound/repo_tree_generator.md)

## 3. Dependencies

*   `pathspec`: For parsing `.gitignore` patterns.

## 4. Implementation Details

The adapter performs a recursive walk of the project directory. For each file and directory, it checks against a `PathSpec` object initialized with patterns from the `.gitignore` file plus a set of default ignores (e.g., `.git/`, `.venv/`). This ensures the generated tree is a clean representation of the project's tracked files. The implementation correctly handles directory-specific patterns (e.g., `dist/`) by adding a trailing slash before checking against the pathspec.
