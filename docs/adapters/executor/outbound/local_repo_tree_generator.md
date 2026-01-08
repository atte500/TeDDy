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

### `.teddyignore` Precedence Logic
**Introduced in:** [./../../slices/executor/14-teddyignore-override.md](./../../slices/executor/14-teddyignore-override.md)
**Status:** Implemented

To provide ultimate control over the AI's context, the generator also supports a `.teddyignore` file in the project root. This file uses the same syntax as `.gitignore`, but its rules are applied with higher precedence. This is achieved by loading patterns in a specific order:

1.  **Base Rules:** All patterns from all `.gitignore` files are loaded first.
2.  **Override Rules:** Patterns from the root `.teddyignore` file are loaded last.

The combined list is passed to the `pathspec` library. Because `pathspec` honors the "last match wins" principle, a negation pattern (e.g., `!dist/index.html`) in `.teddyignore` will correctly override a broader ignore pattern (e.g., `dist/`) from a `.gitignore` file.

This ensures a clean separation between the version control context and the context supplied to the AI.
