# System Architecture: TeDDy

This document outlines the technical standards, conventions, and setup process for the `TeDDy` project, which currently consists of the `executor` and `tui` packages.

## 1. Setup Checklist

This checklist guides the initial setup of the project environment. Each step must be completed in order.

- [x] Verify system prerequisites (Python 3.9+, pip, Poetry).
- [x] Create the initial source code directory structure for the `executor` package (`packages/executor/src/teddy_executor`).
- [x] Create the test directory structure for the `executor` package (`packages/executor/tests/...`).
- [x] Create a root `.gitignore` file.
- [x] Create the `pyproject.toml` file for the `executor` package.
- [x] Install project dependencies for a specific package (e.g., `cd packages/executor && poetry install`).
- [x] Initialize pre-commit hooks from the root directory.
- [x] Run the initial test suite to verify the setup (e.g., `cd packages/executor && poetry run pytest`).

## 2. Conventions & Standards

### Language & Runtime
- **Language:** Python
- **Version:** 3.9+

### Dependency Management
- **Tool:** `Poetry`.
- **Usage:** Dependencies are defined in `pyproject.toml` within each package. The `executor` package is configured as an installable CLI tool. Once installed via `poetry -C packages/executor install`, the `teddy` command is available within the activated Poetry shell. For development tasks from the project root, commands must be directed to the correct package, e.g., `poetry -C packages/executor run ...`.

### Version Control Strategy
- **System:** Git
- **Branching:** Trunk-Based Development on the `main` branch.
- **Commit Messages:** Must follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification.

### CI/CD Strategy
- **Platform:** GitHub Actions.
- **Triggers:** On every push to the `main` branch.
- **Pipeline:** The CI pipeline will lint, type-check, test, and build the packages.

### Service Layer Naming Convention
- **Dependency Attributes:** Injected dependencies in the core application services (`packages/executor/src/teddy_executor/core/services/`) MUST be private.
- **Rationale:** This enforces a consistent pattern across the service layer, clearly distinguishing injected dependencies from public methods or other attributes.

### Testing Strategy
- **Framework:** `pytest`.
- **Location of Tests:** Within each package, tests are organized as follows:
    - `tests/acceptance/`: End-to-end tests.
    - `tests/integration/`: Tests for components that interact with external systems.
    - `tests/unit/`: Tests for individual functions or classes in isolation.
- **Execution:** Tests are run from the **project root** by directing poetry to the correct package.
    - **Run all tests for a package:** `poetry -C packages/executor run pytest`
    - **Run tests in a specific file:** `poetry -C packages/executor run pytest tests/acceptance/test_chat_with_user_action.py`
    - **Run a specific test by name:** `poetry -C packages/executor run pytest -k "test_chat_with_user_gets_response"`

### Pre-commit Hooks
- **Framework:** `pre-commit`.
- **Configuration:** Stored in `.pre-commit-config.yaml` at the repository root.
- **Included Hooks:**
    - `ruff`: For linting and formatting.
    - `mypy`: For static type checking.
    - `check-yaml`, `check-toml`: For syntax validation.

### Spike Directory Exclusion
The `spikes/` directory is intentionally excluded from `ruff` and `mypy` checks in `.pre-commit-config.yaml`.
- **Rationale:** Spikes are for rapid, isolated experimentation. The code within them is temporary and not expected to meet production quality standards. Enforcing linting would hinder their exploratory purpose.

### Handling of Secrets
- **Strategy:** Not applicable for this tool. If third-party API keys are needed in the future, they will be managed through environment variables.

### Running Scripts (including Spikes) from the Root
When running a script from the project root using Poetry, it's crucial to understand that the `-C` flag changes the effective working directory before the command is executed. For example, `poetry -C packages/executor run ...` will execute the command as if you were inside the `packages/executor/` directory.

Consequently, any paths to files outside this directory (like those in the root `/spikes` folder) must be relative *from that new working directory*.

- **Correct Pattern:** Use `../..` to navigate up from the package directory to the project root.
- **Example:** To run a spike from the root while inside the `teddy-executor` virtual environment:
  ```bash
  # Correctly navigates up two levels to the root, then down into spikes.
  poetry -C packages/executor run python ../../spikes/technical/my_spike.py
  ```

### Third-Party Dependency Vetting
- **Strategy:** Mandate a "Verify, Then Document" Spike for new dependencies.
- **Rationale:** Based on the RCA for a failure involving the `gitwalk` library ([see RCA](./rca/unreliable-third-party-library-gitwalk.md)), new third-party dependencies must be de-risked before integration.
- **Process:** Before a new dependency is used, a minimal technical spike must prove its core functionality. The successful spike script should be referenced in the final adapter design document.

---

## 3. Component Design

This section provides a canonical map of the major architectural components for each package.

### `executor` Package

#### Hexagonal Core
*   **Domain Model:** The central business logic and state.
    *   [Domain Model & Ubiquitous Language](./contexts/executor/domain_model.md)
    *   [ExecutionReport](./contexts/executor/domain/execution_report.md)
*   **Inbound Ports:** Define how the application is driven.
    *   [IGetContextUseCase](./contexts/executor/ports/inbound/get_context_use_case.md)
    *   [IRunPlanUseCase](./contexts/executor/ports/inbound/run_plan_use_case.md)
*   **Outbound Ports:** Define interfaces for external dependencies.
    *   [IEnvironmentInspector](./contexts/executor/ports/outbound/environment_inspector.md)
    *   [IFileSystemManager](./contexts/executor/ports/outbound/file_system_manager.md)
    *   [IRepoTreeGenerator](./contexts/executor/ports/outbound/repo_tree_generator.md)
    *   [IShellExecutor](./contexts/executor/ports/outbound/shell_executor.md)
    *   [IUserInteractor](./contexts/executor/ports/outbound/user_interactor.md)
    *   [IWebScraper](./contexts/executor/ports/outbound/web_scraper.md)
    *   [IWebSearcher](./contexts/executor/ports/outbound/web_searcher.md)
*   **Application Services:** Orchestrate the core logic.
    *   [ActionDispatcher](./contexts/executor/services/action_dispatcher.md)
    *   [ActionFactory](./contexts/executor/services/action_factory.md)
    *   [ContextService](./contexts/executor/services/context_service.md)
    *   [ExecutionOrchestrator](./contexts/executor/services/execution_orchestrator.md)
    *   [PlanParser](./contexts/executor/services/plan_parser.md)

#### Primary Adapters
*   **Inbound Adapters:** Drive the application's core.
    *   [CLI Adapter](./adapters/executor/inbound/cli.md)
*   **Outbound Adapters:** Implement outbound ports to interact with external systems.
    *   [ConsoleInteractorAdapter](./adapters/executor/outbound/console_interactor.md)
    *   [LocalFileSystemAdapter](./adapters/executor/outbound/local_file_system_adapter.md)
    *   [LocalRepoTreeGenerator](./adapters/executor/outbound/local_repo_tree_generator.md)
    *   [ShellAdapter](./adapters/executor/outbound/shell_adapter.md)
    *   [SystemEnvironmentInspector](./adapters/executor/outbound/system_environment_inspector.md)
    *   [WebScraperAdapter](./adapters/executor/outbound/web_scraper_adapter.md)
    *   [WebSearcherAdapter](./adapters/executor/outbound/web_searcher_adapter.md)

---

## 4. Project Stages & Polar Stars

This section tracks the high-level project stages. Each stage delivers a significant set of features guided by a "Polar Star" prototype.

| Status | Stage                         | Description                                                                                                                                                          | Polar Star |
| :----: | ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------: |
|   ✅    | **Stage 01: CLI Executor**    | Delivered the core `teddy` command-line tool for plan execution. Implemented all foundational actions, the context utility, and established the YAML-based workflow. |    N/A     |
|   📝    | **Stage 02: Interactive TUI** | Create a Terminal User Interface to streamline the workflow of interacting with the AI agents, managing context, and executing plans without leaving the terminal.   | `Planned`  |
---

## 5. Key Architectural Decisions

This section captures significant, long-standing architectural decisions and patterns that define the system's design.

-   **Hexagonal Architecture:** The core business logic is isolated from external frameworks and I/O, enabling independent testing and technology swapping.
-   **Dependency Injection (DI):** The composition root in `main.py` uses the `punq` library to manage and inject dependencies, decoupling services from concrete implementations.
-   **"White-Box" Acceptance Testing:** All acceptance tests use `typer.testing.CliRunner` to run the CLI application in-process. This is the required pattern as it ensures mocks are respected and is faster and more reliable than testing via `subprocess`.
-   **Structured Output Parsing in Tests:** Acceptance tests that verify structured output (e.g., YAML) MUST parse the output into a data structure before making assertions. This makes tests resilient to formatting changes.
-   **Separation of I/O Concerns:** The `--plan-file` CLI option is the canonical way to provide a plan, reserving `stdin` exclusively for interactive prompts (like `y/n` or `chat_with_user`).
-   **Context Configuration:** The `context` command's behavior is explicitly driven by the contents of `.teddy/*.context` files, providing a clear, user-configurable contract.
