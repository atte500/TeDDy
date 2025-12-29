# Outbound Adapter: `LocalRepoTreeGeneratorAdapter`

- **Status:** Planned
- **Introduced in:** [Slice 13: Implement `context` Command](./../../../slices/13-context-command.md)

This adapter provides a concrete implementation of the `IRepoTreeGenerator` port, responsible for scanning the local file system and generating a textual representation of the repository tree.

## Implemented Ports
- [IRepoTreeGenerator](../../core/ports/outbound/repo_tree_generator.md)

## Implementation Notes

### De-risking
A technical spike was deemed unnecessary for this component. The task of walking a file system and filtering based on `.gitignore` rules is a common requirement with standard, well-documented solutions in Python.

### Strategy
The implementation will follow these steps:
1.  **Read `.gitignore`:** The adapter will first look for a `.gitignore` file in the current working directory. If found, it will parse its patterns. The `pathspec` library is the recommended tool for this task as it correctly handles the `.gitignore` pattern syntax.
2.  **Walk the Directory Tree:** The adapter will recursively walk the directory structure starting from the current working directory. Python's `pathlib.Path.rglob('*')` or `os.walk()` are suitable for this.
3.  **Filter Paths:** For each file and directory found, the adapter will use the parsed `.gitignore` patterns (from `pathspec`) to determine if the path should be ignored.
4.  **Format Output:** The remaining (non-ignored) paths will be collected and formatted into a hierarchical, multi-line string that visually represents the repository tree. Common directories that are typically ignored (e.g., `.git`, `__pycache__`, `.venv`) will be excluded by default, even if not present in `.gitignore`.

## External Documentation
- Python `pathlib` module: [https://docs.python.org/3/library/pathlib.html](https://docs.python.org/3/library/pathlib.html)
- `pathspec` library on PyPI: [https://pypi.org/project/pathspec/](https://pypi.org/project/pathspec/)
