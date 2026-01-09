# RCA: `UnicodeEncodeError` and Suboptimal `repotree` Format

## 1. Summary
The `teddy context` command was failing in the Windows CI environment with a `UnicodeEncodeError`. The **immediate cause** was the use of Unicode box-drawing characters to render a visual file tree, which are not supported by the default Windows console encoding (`cp1252`).

The **architectural root cause**, identified during this investigation, was the use of a human-readable visual format for data intended for a machine (LLM) consumer. This format was inefficient, complex to generate, and introduced the platform-specific encoding fragility. The fix is to replace the visual tree with a simple, reliable, and token-efficient indented list format.

## 2. Root Cause
1.  **Immediate Cause:** A `UnicodeEncodeError` was triggered because the `_TreeFormatter` used Unicode characters (`└──`, `├──`) that are not part of the `cp1252` character map, the default on Windows.
2.  **Architectural Cause:** The choice to generate a visual tree was a suboptimal design for machine-to-machine communication. This format conflated data (the file list) with presentation, leading to unnecessary complexity, token inefficiency for the LLM, and the platform-specific bug.

## 3. Verified Solution (Architectural Improvement)
The solution is to replace the visual tree generation logic in `packages/executor/src/teddy_executor/adapters/outbound/local_repo_tree_generator.py` entirely. The new implementation should generate a simple, space-indented list of files and directories. This format is 100% platform-agnostic, more token-efficient, and easier for an LLM to parse.

**Recommended Implementation:**

In `local_repo_tree_generator.py`, replace the `_TreeFormatter` class with the following, and update the `generate_tree` method to use it.

```python
from pathlib import Path

class _IndentedListFormatter:
    """
    A helper class to format a set of paths into a simple, indented list
    that is reliable and easy for an LLM to parse.
    """

    def __init__(self, root_dir: Path, included_paths: set[Path]):
        self.root_dir = root_dir
        self.included_paths = included_paths

    def format(self) -> str:
        """Generates the indented list string."""
        tree_lines = []
        self._format_recursive(self.root_dir, 0, tree_lines)
        return "\n".join(tree_lines)

    def _format_recursive(self, directory: Path, level: int, tree_lines: list[str]):
        """Recursively builds the tree string."""
        children = sorted(
            [p for p in directory.iterdir() if p in self.included_paths],
            key=lambda p: (not p.is_dir(), p.name.lower()),
        )

        indent = "  " * level
        for path in children:
            entry = f"{path.name}/" if path.is_dir() else path.name
            tree_lines.append(f"{indent}{entry}")

            if path.is_dir():
                self._format_recursive(path, level + 1, tree_lines)

# The `generate_tree` method in `LocalRepoTreeGenerator` should be updated as follows:
#
# def generate_tree(self) -> str:
#     included_paths = self._get_included_paths()
#     formatter = _IndentedListFormatter(self.root_dir, included_paths)
#     return formatter.format()
```

## 4. Preventative Measures (Architectural Recommendation)
**Recommendation:** For any data intended for machine consumption (e.g., an LLM), always use a simple, structured data format (like a newline-delimited or indented list) instead of a human-readable presentation format. This decouples the data from its presentation, improving reliability, efficiency, and simplicity.

## 5. Recommended Regression Test
The acceptance test `test_context_command_honors_teddyignore_overrides` should be updated to assert the presence of the new indented list format in the final output.

**Example assertion update in `tests/acceptance/test_context_command.py`:**

```python
def test_context_command_honors_teddyignore_overrides(tmp_path: Path):
    # ... (Arrange section is unchanged)

    # Act
    result = run_teddy_command(args=["context"], cwd=tmp_path)

    # Assert
    assert result.returncode == 0, f"Teddy exited with an error:\n{result.stderr}"

    output = result.stdout

    # Expected output snippet inside the 'repotree.txt' part of the context:
    expected_tree_snippet = (
        "dist/\n"
        "  index.html"
    )

    assert expected_tree_snippet in output
    assert "bundle.js" not in output
```
