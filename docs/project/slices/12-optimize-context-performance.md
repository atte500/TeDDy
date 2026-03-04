# Slice 12: Optimize Context Performance

## Business Goal
Reduce `teddy context` execution time from ~2 seconds to under 200ms for standard repositories by replacing inefficient full-disk scans with pruning-aware directory traversal.

## Acceptance Criteria
- **Scenario: Performance Benchmark**
  - Given a repository with large ignored directories (e.g., `.venv`, `node_modules` containing >10,000 files).
  - When I run `time poetry run teddy context --no-copy`.
  - Then the command should complete in less than 200ms.
- **Scenario: Tree Integrity**
  - Given a repository with a mix of ignored and non-ignored files.
  - When I run `teddy context`.
  - Then the generated "Repository Tree" must accurately reflect the project structure, showing all non-ignored files and their parent directories.
- **Scenario: Regression Check**
  - When I run `poetry run pytest tests/unit/adapters/outbound/test_local_repo_tree_generator.py`.
  - Then all existing tree generation tests must pass.

## Architectural Changes
- **Component:** `LocalRepoTreeGenerator` (`src/teddy_executor/adapters/outbound/local_repo_tree_generator.py`)
- **Change:** Replace the use of `Path.rglob("**/*")` in `_get_included_paths` with a manual recursive walk (using `Path.iterdir()`) that prunes directories as soon as they match an ignore pattern.

## Scope of Work
- [ ] Refactor `LocalRepoTreeGenerator._get_included_paths` to use a recursive helper function (e.g., `_walk(current_dir)`).
- [ ] For each entry in a directory:
  - Construct the relative path string (adding a trailing `/` if it is a directory).
  - Check the entry against `self.ignore_spec.match_file(match_path)`.
  - If it is ignored, **skip it and do not recurse** (pruning).
  - If it is not ignored:
    - Add the path to the `included_paths` set.
    - If it is a directory, recurse into it.
- [ ] Ensure that for every included file, all its parent directories (up to `root_dir`) are also added to the `included_paths` set to maintain tree connectivity.
- [ ] Run the `time` command to verify the performance fix on the current TeDDy repo.
