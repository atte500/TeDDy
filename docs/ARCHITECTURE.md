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
- **Tool:** `Poetry`.
- **Usage:** Dependencies are defined in `pyproject.toml` and managed via the `poetry` CLI. To install dependencies, run `poetry install`. The use of virtual environments is managed automatically by Poetry. All commands, including running Python scripts or tests, **must** be prefixed with `poetry run` to ensure they execute within the project's virtual environment (e.g., `poetry run python ...`, `poetry run pytest`).

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

#### Spike Directory Exclusion
The `spikes/` directory is intentionally excluded from `ruff` and `mypy` checks. This is configured in the `[tool.ruff]` and `[tool.mypy]` sections of `pyproject.toml`.
- **Rationale:** Spikes are for rapid, isolated experimentation. The code within them is often temporary, may not conform to the project's quality standards, and might intentionally contain errors (e.g., to reproduce a bug). Enforcing linting and type-checking on this directory would hinder the exploratory purpose of spikes.

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

### Slice 02: Implement `create_file` Action

*   **Core Logic:**
    *   [Domain Model (Updated)](./core/domain_model.md)
    *   [Application Service: PlanService (Updated)](./core/services/plan_service.md)
    *   [Outbound Port: FileSystemManager](./core/ports/outbound/file_system_manager.md)
*   **Adapters:**
    *   [Outbound Adapter: LocalFileSystemAdapter](./adapters/outbound/file_system_adapter.md)

### Slice 03: Refactor Action Dispatching

*   **Core Logic:**
    *   [Domain Model (Refactored)](./core/domain_model.md)
    *   [Action Factory](./core/factories/action_factory.md)
    *   [Application Service: PlanService (Refactored)](./core/services/plan_service.md)

### Slice 04: Implement `read` Action

*   **Core Logic:**
    *   [Domain Model (Updated)](./core/domain_model.md)
    *   [Application Service: PlanService (Updated)](./core/services/plan_service.md)
    *   [Action Factory (Updated)](./core/factories/action_factory.md)
    *   [Outbound Port: FileSystemManager (Updated)](./core/ports/outbound/file_system_manager.md)
    *   [Outbound Port: WebScraper](./core/ports/outbound/web_scraper.md)
*   **Adapters:**
    *   [Outbound Adapter: WebScraperAdapter](./adapters/outbound/web_scraper_adapter.md)
    *   [Outbound Adapter: LocalFileSystemAdapter (Updated)](./adapters/outbound/file_system_adapter.md)

## 4. Vertical Slices

This section will list the architectural documents for each vertical slice as they are defined.

*   [✅] [Slice 01: Walking Skeleton](./slices/01-walking-skeleton.md)
*   [✅] [Slice 02: Implement `create_file` Action](./slices/02-create-file-action.md)
*   [✅] [Slice 03: Refactor Action Dispatching](./slices/03-refactor-action-dispatching.md)
*   [✅] [Slice 04: Implement `read` Action](./slices/04-read-action.md)
*   [✅] [Slice 05: Refactor Test Setup](./slices/05-refactor-test-setup.md)

---

## 5. Architectural Notes & Technical Debt

This section captures non-blocking architectural observations and potential areas for future refactoring that are identified during development.

- ~~**Test Setup Maintainability (from Slice 04):**~~ (Resolved in Slice 05) During the implementation of the `read` action, adding a new dependency (`WebScraper`) to the `PlanService` constructor caused a cascade of failures throughout the unit test suite. Each test had to be manually updated to provide a mock for the new dependency. This indicated that the test setup was brittle. This was resolved by introducing shared `pytest` fixtures for instantiating the `PlanService` and its dependencies to improve maintainability.
- **Refactoring Impact (from Slice 03):** The change from a generic `Action` model with a `params` dictionary to specific `Action` subclasses (`ExecuteAction`, `CreateFileAction`) had a wider impact than initially anticipated. It required changes not only in the core logic (`PlanService`) but also in the composition root (`main.py`) and any adapter that interacted with the action models for reporting (`CLIFormatter`). This experience highlights that domain model refactoring often has broad consequences and reinforces the critical importance of a comprehensive, full-suite (unit, integration, and acceptance) verification step to catch downstream regressions.
- ~~**Action Validation Logic:**~~ (Resolved in Slice 03) The `Action` domain model's `__post_init__` method currently acts as a router for parameter validation based on `action_type`. As more action types are added, this could violate the Single Responsibility Principle (SRP). A future refactoring could move this validation logic to a dedicated Factory or Strategy pattern to improve separation of concerns.
- ~~**Action Dispatching in PlanService:**~~ (Resolved in Slice 03) The `PlanService._execute_single_action` method uses an `if/elif` chain to dispatch actions. This is acceptable for a small number of actions but will become a maintenance bottleneck as the system grows. This should be refactored to a more scalable pattern, such as the Command or Strategy pattern.
