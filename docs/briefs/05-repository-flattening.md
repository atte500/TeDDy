# Architectural Brief: Foundational Restructuring

## 1. Goal (The "Why")

The strategic goal is to refactor the project's foundational structure to improve developer experience, simplify maintenance, and establish core services. This is a strategic prerequisite that unblocks all subsequent feature development by creating a clean, stable, and ergonomic codebase.

This brief is based on the full specification defined in [foundational-restructuring.md](/docs/specs/foundational-restructuring.md).

## 2. Proposed Solution (The "What")

The solution is a pure architectural refactoring initiative comprised of three distinct activities:

1.  **Repository Flattening:** The legacy `packages/executor` directory will be eliminated. All core source code will be moved to a root-level `src/` directory. This will simplify the development workflow, dependency management, and CI/CD scripts. The obsolete `packages/tui/` directory will also be removed.

## 3. Implementation Analysis (The "How")

The codebase exploration confirms that this refactoring is primarily a task of moving files and updating configuration. No core application logic needs to be changed, but several key configuration files that assume the `packages/executor` structure must be updated.

-   **Source Code & Tests:** The entire contents of `packages/executor/src/teddy_executor` will be moved to `src/teddy_executor`, and `packages/executor/tests` will be moved to `tests`.
-   **Dependency Management:** The `[tool.poetry]` dependencies, scripts, and groups from `packages/executor/pyproject.toml` must be merged into the root `pyproject.toml`. The root file will become the single source of truth for the project's dependencies.
-   **CI/CD Pipeline:** The `.github/workflows/ci.yml` file must be updated to remove all references to `working-directory: ./packages/executor` and adjust the cache path for the virtual environment.
-   **Pre-commit Hooks:** The `.pre-commit-config.yaml` must be modified to remove the `poetry -C packages/executor` prefix from all commands, as they will now run from the project root.
-   **Documentation Impact:** A significant number of documentation files currently reference the old `packages/executor` path. While a full update is part of a later theme, this work will render those instructions temporarily incorrect.

## 4. Vertical Slices

This brief will be implemented as a single, comprehensive vertical slice. The order of operations is critical to ensure a clean transition.

-   **[ ] Task: Relocate Core Files**
    -   Move the contents of `packages/executor/src/` to a new root-level `src/` directory.
    -   Move the contents of `packages/executor/tests/` to a new root-level `tests/` directory.

-   **[ ] Task: Consolidate `pyproject.toml`**
    -   Merge all dependencies, dev dependencies, and scripts from `packages/executor/pyproject.toml` into the root `pyproject.toml`.
    -   Update the `[tool.poetry.packages]` definition in the root `pyproject.toml` to point to the new `src` directory.
    -   Delete `packages/executor/pyproject.toml` and `packages/executor/poetry.lock`.

-   **[ ] Task: Update CI & Pre-commit Configuration**
    -   In `.github/workflows/ci.yml`, remove all `working-directory` keys pointing to the old package and update the cache path.
    -   In `.pre-commit-config.yaml`, update all hooks to run `poetry run` directly from the project root.

-   **[ ] Task: Clean Up Old Structure**
    -   Delete the now-empty `packages/` directory.
    -   Delete the obsolete `packages/tui/` directory as originally planned.

-   **[ ] Task: Verify the Transition**
    -   Run `poetry lock` and `poetry install` from the project root to ensure dependencies resolve correctly.
    -   Run the full test suite (`poetry run pytest`) to confirm that all tests pass with the new structure.
