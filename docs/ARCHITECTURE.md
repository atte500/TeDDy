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

### Third-Party Dependency Vetting
- **Strategy:** Mandate a "Verify, Then Document" Spike for new dependencies.
- **Rationale:** Based on the RCA for a failure involving the `gitwalk` library ([see RCA](./rca/unreliable-third-party-library-gitwalk.md)), a key architectural principle is to de-risk new third-party dependencies before they are integrated.
- **Process:** Before a new, non-trivial dependency is formally documented in an adapter design, a minimal technical spike **must** be created and successfully run. This spike's purpose is to prove that the library's core advertised feature works as expected and that its API contract is sound. The successful spike script should then be referenced in the final adapter design document as proof of verification.

#### Spike Directory Exclusion
The `spikes/` directory is intentionally excluded from `ruff` and `mypy` checks. This is configured in the `[tool.ruff]` and `[tool.mypy]` sections of `pyproject.toml`.
- **Rationale:** Spikes are for rapid, isolated experimentation. The code within them is often temporary, may not conform to the project's quality standards, and might intentionally contain errors (e.g., to reproduce a bug). Enforcing linting and type-checking on this directory would hinder the exploratory purpose of spikes.

### Handling of Secrets
- **Strategy:** Not applicable for this tool. If third-party API keys (e.g., for `research`) are needed in the future, they will be managed through environment variables and a `.env` file (which will be git-ignored).

### Debug Mode
- **Strategy:** A global `--debug` flag will be implemented. When enabled, it will set the logging level to `DEBUG`, providing verbose output for both the executor's operations and the output of any subprocesses.

### Third-Party Dependency Vetting
- **Strategy:** Mandate a "Verify, Then Document" Spike for new dependencies.
- **Rationale:** Based on the RCA for a failure involving the `gitwalk` library ([see RCA](./rca/unreliable-third-party-library-gitwalk.md)), a key architectural principle is to de-risk new third-party dependencies before they are integrated.
- **Process:** Before a new, non-trivial dependency is formally documented in an adapter design, a minimal technical spike **must** be created and successfully run. This spike's purpose is to prove that the library's core advertised feature works as expected and that its API contract is sound. The successful spike script should then be referenced in the final adapter design document as proof of verification.

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
    *   [Action Factory](./core/services/action_factory.md)
    *   [Application Service: PlanService (Refactored)](./core/services/plan_service.md)

### Slice 04: Implement `read` Action

*   **Core Logic:**
    *   [Domain Model (Updated)](./core/domain_model.md)
    *   [Application Service: PlanService (Updated)](./core/services/plan_service.md)
    *   [Action Factory (Updated)](./core/services/action_factory.md)
    *   [Outbound Port: FileSystemManager (Updated)](./core/ports/outbound/file_system_manager.md)
    *   [Outbound Port: WebScraper](./core/ports/outbound/web_scraper.md)
*   **Adapters:**
    *   [Outbound Adapter: WebScraperAdapter](./adapters/outbound/web_scraper_adapter.md)
    *   [Outbound Adapter: LocalFileSystemAdapter (Updated)](./adapters/outbound/file_system_adapter.md)

### Slice 06: Implement `edit` Action

*   **Core Logic:**
    *   [Domain Model (Updated)](./core/domain_model.md)
    *   [Application Service: PlanService (Updated)](./core/services/plan_service.md)
    *   [Action Factory (Updated)](./core/services/action_factory.md)
    *   [Outbound Port: FileSystemManager (Updated)](./core/ports/outbound/file_system_manager.md)
*   **Adapters:**
    *   [Outbound Adapter: LocalFileSystemAdapter (Updated)](./adapters/outbound/file_system_adapter.md)

### Slice 07: Update Action Failure Behavior

*   **Core Logic:**
    *   [Domain Model (Updated)](./core/domain_model.md)
    *   [Application Service: PlanService (Updated)](./core/services/plan_service.md)
    *   [Outbound Port: FileSystemManager (Updated)](./core/ports/outbound/file_system_manager.md)
*   **Adapters:**
    *   [Outbound Adapter: LocalFileSystemAdapter (Updated)](./adapters/outbound/file_system_adapter.md)

### Slice 10: Implement `chat_with_user` Action

*   **Core Logic:**
    *   [Domain Model (Updated)](./core/domain_model.md)
    *   [Application Service: PlanService (Updated)](./core/services/plan_service.md)
    *   [Application Service: ActionFactory (Updated)](./core/services/action_factory.md)
    *   [Outbound Port: `IUserInteractor`](./core/ports/outbound/user_interactor.md)
*   **Adapters:**
    *   [Outbound Adapter: `ConsoleInteractorAdapter`](./adapters/outbound/console_interactor.md)

### Slice 11: Refactor Execution Report to Pure YAML

*   **Adapters:**
    *   [Inbound Adapter: CLI Formatter (Refactored)](./adapters/inbound/cli.md)
*   **Testing:**
    *   All acceptance tests will be refactored to parse YAML.

### Slice 12: Implement `research` Action

*   **Core Logic:**
    *   [Domain Model (Updated)](./core/domain_model.md)
    *   [Action Factory (Updated)](./core/services/action_factory.md)
    *   [Application Service: PlanService (Updated)](./core/services/plan_service.md)
    *   [Outbound Port: `IWebSearcher`](./core/ports/outbound/web_searcher.md)
*   **Adapters:**
    *   [Outbound Adapter: `WebSearcherAdapter`](./adapters/outbound/web_searcher_adapter.md)

### Slice 13: Implement `context` Command

*   **Core Logic:**
    *   [Domain Model (Updated)](./core/domain_model.md)
    *   [Inbound Port: `IGetContextUseCase`](./core/ports/inbound/get_context_use_case.md)
    *   [Outbound Port: `IRepoTreeGenerator`](./core/ports/outbound/repo_tree_generator.md)
    *   [Outbound Port: `IEnvironmentInspector`](./core/ports/outbound/environment_inspector.md)
    *   [Application Service: `ContextService`](./core/services/context_service.md)
*   **Adapters:**
    *   [Outbound Adapter: `LocalRepoTreeGenerator`](./adapters/outbound/local_repo_tree_generator.md)
    *   [Outbound Adapter: `SystemEnvironmentInspector`](./adapters/outbound/system_environment_inspector.md)
*   **Root Cause Analysis:**
    *   [RCA: Unreliable Third-Party Library (`gitwalk`)](./rca/unreliable-third-party-library-gitwalk.md)

## 4. Vertical Slices

This section will list the architectural documents for each vertical slice as they are defined.

*   [x] [Slice 01: Walking Skeleton](./slices/01-walking-skeleton.md)
*   [x] [Slice 02: Implement `create_file` Action](./slices/02-create-file-action.md)
*   [x] [Slice 03: Refactor Action Dispatching](./slices/03-refactor-action-dispatching.md)
*   [x] [Slice 04: Implement `read` Action](./slices/04-read-action.md)
*   [x] [Slice 05: Refactor Test Setup](./slices/05-refactor-test-setup.md)
*   [x] [Slice 06: Implement `edit` Action](./slices/06-edit-action.md)
*   [x] [Slice 07: Update Action Failure Behavior](./slices/07-update-action-failure-behavior.md)
*   [x] [Slice 08: Refactor Action Dispatching](./slices/08-refactor-action-dispatching.md)
*   [x] [Slice 09: Enhance `edit` Action Safety](./slices/09-enhance-edit-action-safety.md)
*   [x] [Slice 10: Implement `chat_with_user` Action](./slices/10-chat-with-user-action.md)
*   [x] [Slice 11: Refactor Execution Report to Pure YAML](./slices/11-refactor-report-to-yaml.md)
*   [x] [Slice 12: Implement `research` action](./slices/12-research-action.md)
*   [ ] [Slice 13: Implement `context` Command](./slices/13-context-command.md)

---

## 5. Architectural Notes & Technical Debt

This section captures non-blocking architectural observations and potential areas for future refactoring that are identified during development.

- **CLI Exit Code Philosophy (from Slice 06):** An architectural decision was made to define the application's exit code behavior. The chosen philosophy is that the application process should exit with a non-zero code if *any* action within a plan fails. This aligns the tool with standard CI/CD practices, where a non-zero exit code universally signals failure. This decision required refactoring older acceptance tests that previously expected an exit code of `0` even when a plan's business logic failed.
- **Consistent Failure Reporting (from Slice 07):** A systemic inconsistency in failure reporting was identified during development. The `CLIFormatter` now handles all `FAILURE` statuses uniformly, producing a consistent, YAML-style block for the details of any failed action. This improves both human and machine readability and should be considered the standard pattern for all future failure reporting. This change necessitated refactoring a significant number of existing acceptance and integration tests to align with the new, more robust output format.
- **Static Analysis vs. Dynamic Patterns (from Slice 08):** The refactoring of `PlanService` to use a dynamic dispatch map (`{ActionType: handler_method}`) introduced a challenge for the static type checker, `mypy`. While the pattern is robust at runtime, `mypy` could not statically verify the type relationship between the dispatched action and its handler, resulting in a `[operator]` error. The issue was resolved pragmatically by adding a `# type: ignore` comment. This captures a recurring architectural trade-off: highly dynamic, decoupled patterns can sometimes conflict with the guarantees of static analysis, requiring targeted suppression of type errors.
- **Clarification on Interactivity (from Slice 10):** An initial design spike for the `chat_with_user` action conflated two distinct concepts: (1) a specific action for free-text user interaction, and (2) the global `y/n` approval mechanism that applies to *all* actions. The spike process clarified this. The architectural decision is that interactive approval is a global, wrapper feature of the executor's CLI, while `chat_with_user` is a discrete action type within a plan that handles long-form prompts and captures free-text responses.
- **Consolidation of Test Helpers (from Slice 10):** During development, it was noted that every acceptance test file duplicated the logic for running `teddy` as a subprocess. This was refactored by creating a central `tests/acceptance/helpers.py` module to consolidate this logic, improving maintainability. This refactoring also highlighted the need for different invocation strategies for interactive vs. non-interactive tests.
- **CLI Input Strategy (from Slice 10):** The implementation of an interactive action (`chat_with_user`) revealed a design flaw: the application was using `stdin` for both plan input and interactive user input, creating a conflict. This was resolved by adding a dedicated `--plan-file` CLI option, establishing a pattern where `stdin` is reserved for interactive I/O while file-based input is used for non-interactive plan delivery in tests.
- **Acceptance Testing Strategy for Network I/O (from Slice 12):** The `research` action implementation revealed a limitation of using `unittest.mock.patch` for acceptance tests that run the application as a separate subprocess (e.g., via `subprocess.run`). Mocks applied in the test runner process do not affect the separate application process. This led to a refactoring of the `research` acceptance test to run "in-process" by directly instantiating the `PlanService` and injecting a mocked adapter. This "white-box" acceptance testing strategy is now the recommended approach for features involving network I/O to ensure tests are fast, reliable, and do not make real network calls.
- **YAML Formatting for Readability (from Slice 12):** Based on user feedback, a polish task was undertaken to improve the formatting of the final YAML report. Multi-line strings (such as the JSON output from the `research` action) are now formatted using YAML's literal block style (`|`) for improved human readability. This was achieved by implementing a custom string representer for the `PyYAML` library, demonstrating a pattern for controlling fine-grained output formatting.
