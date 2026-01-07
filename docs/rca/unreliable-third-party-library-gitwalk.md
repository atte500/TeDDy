# RCA: Unreliable Third-Party Library (`gitwalk`)

## 1. Summary
The Architect agent's attempt to implement a repository tree generator failed because it relied on the `gitwalk` third-party library. Investigation confirmed that `gitwalk` does not correctly implement the standard `os.walk` contract for directory pruning, making it impossible to prevent the traversal of directories like `.git`. This led to messy, incorrect output. The root cause is twofold: the immediate technical cause is the faulty library, and the systemic cause is a process gap in sufficiently de-risking new, unvetted third-party dependencies before selection.

## 2. Investigation Summary
- **Hypothesis 1 (Confirmed):** The `gitwalk` library is unreliable. A spike (`spikes/debug/01-h1-confirm-bug/reproduce_failure.py`) was created to test its directory pruning behavior. The test confirmed the library does not respect the standard `dirnames[:]` modification, which is the contract for `os.walk`.
- **Hypothesis 2 (Confirmed):** A combination of Python's built-in `os.walk` and the `pathspec` library provides a robust solution. A second spike (`spikes/debug/02-h2-verify-solution/verify_fix.py`) successfully demonstrated that `pathspec` can correctly parse `.gitignore` files and be used to filter both files and directories during an `os.walk` traversal.

## 3. Root Cause
- **Immediate Cause:** The `gitwalk` library is flawed and does not function as documented.
- **Systemic Weakness:** The initial architectural process selected a new dependency based on its description without a sufficient technical spike to verify its core functionality and contracts. This introduced a preventable risk into the development cycle.

## 4. Verified Solution (Immediate Fix)
The `LocalRepoTreeGenerator` adapter should be implemented using Python's standard `os.walk` function and the `pathspec` library. The following code, proven in the solution spike, resolves the immediate issue.

```python
import os
import pathspec

def generate_clean_tree(root_path="."):
    """
    Generates a clean file tree, respecting .gitignore rules.
    This is a simplified representation of the core logic.
    """

    # 1. Load the .gitignore spec
    gitignore_path = os.path.join(root_path, '.gitignore')
    spec = None
    if os.path.exists(gitignore_path):
        with open(gitignore_path, 'r') as f:
            spec = pathspec.PathSpec.from_lines('gitwildmatch', f)

    # 2. Walk the directory
    tree_lines = []
    for root, d_names, f_names in os.walk(root_path, topdown=True):
        # Path relative to the start of the walk
        rel_root = os.path.relpath(root, root_path)
        if rel_root == ".": rel_root = ""

        # 3. Prune directories in-place using the spec
        if spec:
            # Add a trailing slash to test directories
            d_names[:] = [
                d for d in d_names
                if not spec.match_file(os.path.join(rel_root, d) + os.sep)
            ]

        # 4. Filter and process files
        if spec:
            files_to_process = [f for f in f_names if not spec.match_file(os.path.join(rel_root, f))]
        else:
            files_to_process = f_names

        # (Code to format and append to tree_lines would go here)
        for f in files_to_process:
            tree_lines.append(os.path.join(rel_root, f))

    return tree_lines

```

## 5. Preventative Measures (Architectural Recommendation)
To prevent this class of error from recurring, the following architectural process change is recommended:

**Recommendation:** **Mandate a "Verify, Then Document" Spike for New Dependencies.** Before any new third-party dependency is formally documented in an adapter design, a minimal technical spike must be created and successfully run. This spike's purpose is to *prove* that the library's core advertised feature works as expected and that its API contract is sound. The successful spike script should then be referenced or included in the final adapter design document as proof.

## 6. Recommended Regression Test
The following test should be added to the integration test suite for the `LocalRepoTreeGenerator` adapter to ensure gitignore rules are always respected.

```python
import os
from pathlib import Path

# Assuming 'LocalRepoTreeGenerator' is the class implementing the logic
# and it is injected or instantiated for the test.

def test_repo_tree_generator_respects_gitignore(tmp_path: Path):
    """
    Tests that the repo tree generator correctly ignores files and directories
    specified in a .gitignore file.
    """
    # Arrange: Create a test directory structure
    (tmp_path / ".gitignore").write_text("*.log\nignored_dir/\n")
    (tmp_path / "visible_file.txt").write_text("content")
    (tmp_path / "invisible.log").write_text("content")

    ignored_dir = tmp_path / "ignored_dir"
    ignored_dir.mkdir()
    (ignored_dir / "secret.txt").write_text("content")

    visible_dir = tmp_path / "visible_dir"
    visible_dir.mkdir()
    (visible_dir / "another_visible_file.txt").write_text("content")

    # Act: Instantiate the adapter and generate the tree
    # The real implementation will return a formatted string, so the assertions
    # will need to check for the presence/absence of substrings.
    generator = LocalRepoTreeGenerator(start_path=str(tmp_path))
    tree_output = generator.generate_tree()

    # Assert: Check that ignored files/dirs are absent and visible ones are present
    assert "visible_file.txt" in tree_output
    assert "another_visible_file.txt" in tree_output
    assert "visible_dir" in tree_output

    assert "invisible.log" not in tree_output
    assert "ignored_dir" not in tree_output
    assert "secret.txt" not in tree_output
```
