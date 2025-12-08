# System Architecture: `teddy` Executor

This document outlines the technical standards, conventions, and setup process for the `teddy` executor project.

## 1. Setup Checklist

This checklist guides the initial setup of the project environment. Each step must be completed in order.

- [x] Verify system prerequisites (Python 3.9+, pip).
- [x] Create the initial source code directory structure (`src/teddy`).
- [x] Create the test directory structure (`tests/acceptance`, `tests/integration`, `tests/unit`).
- [x] Create a root `.gitignore` file.
- [x] Create the `pyproject.toml` file for dependency and project management.
- [x] Install project dependencies in editable mode.
- [x] Initialize pre-commit hooks.
- [x] Run the initial test suite to verify the setup.

## 2. Conventions & Standards

### Language & Runtime
- **Language:** Python
- **Version:** 3.9+

### Dependency Management
- **Tool:** `pip` with `pyproject.toml`.
- **Usage:** Dependencies are defined in `pyproject.toml`. The project should be installed in editable mode for development using `pip install -e .`. The use of virtual environments (e.g., `venv`) is required. `uv` is a recommended alternative to `pip` for performance.

### Version Control Strategy
- **System:** Git
- **Branching:** Trunk-Based Development on the `main` branch.
- **Commit Messages:** Must follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification.

### CI/CD Strategy
- **Platform:** GitHub Actions.
- **Triggers:** On every push to the `main` branch.
- **Pipeline:** The CI pipeline will lint, type-check, test, and build the package. A separate workflow will handle publishing to PyPI on new version tags.

### Testing Strategy
- **Framework:** `pytest`.
- **Location of Tests:**
    - `tests/acceptance/`: End-to-end tests that run `teddy` as a subprocess.
    - `tests/integration/`: Tests for components that interact with the filesystem or external libraries.
    - `tests/unit/`: Tests for individual functions or classes in isolation.
- **Execution:** Tests are run via the `pytest` command from the project root.

### Pre-commit Hooks
- **Framework:** `pre-commit`.
- **Configuration:** Stored in `.pre-commit-config.yaml`.
- **Included Hooks:**
    - `ruff`: For linting and formatting.
    - `mypy`: For static type checking.
    - `check-yaml`, `check-toml`: For syntax validation.

### Handling of Secrets
- **Strategy:** Not applicable for this tool. If third-party API keys (e.g., for `research`) are needed in the future, they will be managed through environment variables and a `.env` file (which will be git-ignored).

### Debug Mode
- **Strategy:** A global `--debug` flag will be implemented. When enabled, it will set the logging level to `DEBUG`, providing verbose output for both the executor's operations and the output of any subprocesses.

---

## 3. Component Design

This section provides links to the detailed design documents for each component, organized by vertical slice.

### Slice 01: Walking Skeleton

*   **Core Logic:**
    *   [Domain Model](./core/domain_model.md)
    *   [Inbound Port: RunPlanUseCase](./core/ports/inbound/run_plan_use_case.md)
    *   [Outbound Port: ShellExecutor](./core/ports/outbound/shell_executor.md)
    *   [Application Service: PlanService](./core/services/plan_service.md)
*   **Adapters:**
    *   [Inbound Adapter: CLI](./adapters/inbound/cli.md)
    *   [Outbound Adapter: ShellAdapter](./adapters/outbound/shell_adapter.md)

## 4. Vertical Slices

This section will list the architectural documents for each vertical slice as they are defined.

*   [▶️] [Slice 01: Walking Skeleton](./slices/01-walking-skeleton.md)
