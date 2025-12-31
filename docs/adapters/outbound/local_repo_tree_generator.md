# Outbound Adapter: LocalRepoTreeGenerator

-   `**Status:**` Planned
-   **Motivating Vertical Slice:** [Implement `context` Command](../../slices/13-context-command.md)

This adapter is responsible for generating a string representation of the project's file and directory tree, respecting `.gitignore` rules.

## 1. Implemented Ports

*   [IRepoTreeGenerator](../../core/ports/outbound/repo_tree_generator.md)

## 2. Implementation Notes

The implementation will use Python's built-in `os.walk` in combination with the `pathspec` third-party library. This approach was verified by the Debugger agent after a previous attempt with an unreliable library (`gitwalk`) failed. The `pathspec` library correctly parses `.gitignore` files and allows for robust filtering of both files and directories.

In addition to `.gitignore` rules, the implementation will also manually exclude a predefined list of high-noise directories (e.g., `.git`, `.venv`, `__pycache__`) to ensure the cleanest possible output.

### `generate_tree()`

-   `**Status:**` Planned
-   **Logic:**
    1.  Load the `.gitignore` file from the root path into a `pathspec` object. If no `.gitignore` exists, proceed without filtering.
    2.  Define a static set of directories to always exclude (e.g., `.git`).
    3.  Use `os.walk()` to traverse the directory tree from the specified start path.
    4.  During the walk, prune the list of directories to descend into by checking them against both the static exclude list and the `pathspec` object.
    5.  Collect all file paths that are not matched by the `pathspec`.
    6.  Format the final list of directories and files into a human-readable, multi-line tree string.

## 3. Verified Code Snippet (from Debugger RCA)

This snippet demonstrates the core logic of using `os.walk` and `pathspec` to correctly identify files and prune directories.

```python
import os
import pathspec

def get_non_ignored_paths(root_path="."):
    """
    Returns a list of all file paths not ignored by .gitignore.
    """
    gitignore_path = os.path.join(root_path, '.gitignore')
    spec = None
    if os.path.exists(gitignore_path):
        with open(gitignore_path, 'r') as f:
            spec = pathspec.PathSpec.from_lines('gitwildmatch', f)

    paths = []
    for root, d_names, f_names in os.walk(root_path, topdown=True):
        rel_root = os.path.relpath(root, root_path)
        if rel_root == ".": rel_root = ""

        # Prune directories based on the spec
        if spec:
            d_names[:] = [
                d for d in d_names
                if not spec.match_file(os.path.join(rel_root, d) + os.sep)
            ]

        # Filter and collect files
        for f_name in f_names:
            file_path = os.path.join(rel_root, f_name)
            if not spec or not spec.match_file(file_path):
                paths.append(file_path)

    return paths
```

## 4. External Documentation

*   [`pathspec` on PyPI](https://pypi.org/project/pathspec/)
