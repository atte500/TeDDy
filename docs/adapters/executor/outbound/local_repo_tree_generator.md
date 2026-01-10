# Outbound Adapter: `LocalRepoTreeGenerator`

**Status:** Implemented
**Language:** Python 3.9+
**Introduced in:**
- [Slice 13: Implement `context` Command](../../slices/executor/13-context-command.md)
- [Slice 17: Refactor `context` Command Output](../../slices/executor/17-refactor-context-command-output.md)

## 1. Purpose

The `LocalRepoTreeGenerator` is an adapter that implements the `IRepoTreeGenerator` port. It interacts with the local file system to generate a file tree, using the `pathspec` library to correctly parse `.gitignore` and `.teddyignore` files to exclude specified paths.

## 2. Implemented Outbound Port

*   [`IRepoTreeGenerator`](../../contexts/executor/ports/outbound/repo_tree_generator.md)

## 3. Dependencies

*   `pathspec`: For parsing `.gitignore` patterns.

## 4. Implementation Details

### Path Filtering Logic
The adapter performs a recursive walk of the project directory. For each file and directory, it checks against a `PathSpec` object initialized with patterns from ignore files plus a set of default ignores (e.g., `.git/`, `.venv/`). This ensures the generated tree is a clean representation of the project's relevant files.

### Output Generation
**Status:** Planned
The adapter builds the tree structure in memory and returns it as a single, multi-line string. It **does not** write to any intermediate files (e.g., `repotree.txt`). The format is a simple, space-indented list of files and directories, which is the canonical format for providing file hierarchy context to an LLM.

### `.teddyignore` Precedence Logic
**Introduced in:** [Slice 14: Teddyignore Override](../../slices/executor/14-teddyignore-override.md)
**Status:** Implemented

To provide ultimate control over the AI's context, the generator also supports a `.teddyignore` file in the project root. This file uses the same syntax as `.gitignore`, but its rules are applied with higher precedence. This is achieved by loading patterns in a specific order:

1.  **Base Rules:** All patterns from all `.gitignore` files are loaded first.
2.  **Override Rules:** Patterns from the root `.teddyignore` file are loaded last.

The combined list is passed to the `pathspec` library. Because `pathspec` honors the "last match wins" principle, a negation pattern (e.g., `!dist/index.html`) in `.teddyignore` will correctly override a broader ignore pattern (e.g., `dist/`) from a `.gitignore` file.

### `.teddyignore` Precedence Logic
**Introduced in:** [./../../slices/executor/14-teddyignore-override.md](./../../slices/executor/14-teddyignore-override.md)
**Status:** Implemented

To provide ultimate control over the AI's context, the generator also supports a `.teddyignore` file in the project root. This file uses the same syntax as `.gitignore`, but its rules are applied with higher precedence. This is achieved by loading patterns in a specific order:

1.  **Base Rules:** All patterns from all `.gitignore` files are loaded first.
2.  **Override Rules:** Patterns from the root `.teddyignore` file are loaded last.

The combined list is passed to the `pathspec` library. Because `pathspec` honors the "last match wins" principle, a negation pattern (e.g., `!dist/index.html`) in `.teddyignore` will correctly override a broader ignore pattern (e.g., `dist/`) from a `.gitignore` file.

This ensures a clean separation between the version control context and the context supplied to the AI.
