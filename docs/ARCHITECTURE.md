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

### Testing Strategy
- **Framework:** `pytest`.
- **Location of Tests:** Within each package, tests are organized as follows:
    - `tests/acceptance/`: End-to-end tests.
    - `tests/integration/`: Tests for components that interact with external systems.
    - `tests/unit/`: Tests for individual functions or classes in isolation.
- **Execution:** Tests are run from the **project root** by directing poetry to the correct package. For example, to run the `executor` tests: `poetry -C packages/executor run pytest`.

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

## 3. Boundary Map

This section defines the system's strategic architectural divisions, separating isolated business logic from framework-specific integrations.

### `executor` Package

*   **Hexagonal Core:** This contains the pure business logic, application services, and domain models that are independent of any specific delivery mechanism or external tool.
    *   **Components:** `Domain Model`, `Inbound Ports`, `Outbound Ports`, `Application Services`.
*   **Framework/Platform Integration Layer:** This layer contains code that is directly coupled to external frameworks or platforms, such as the command-line interface library (`Typer`). Its primary role is to translate external inputs into calls to the hexagonal core.
    *   **Components:** `main.py` (Composition Root), `CLI Adapter`.
*   **Primary Adapters:** These are the concrete implementations of the outbound ports, bridging the hexagonal core to external systems like the local file system or the console.
    *   **Components:** `ConsoleInteractorAdapter`, `LocalFileSystemAdapter`, `LocalRepoTreeGenerator`, `ShellAdapter`, `SystemEnvironmentInspector`, etc.

---

## 4. Component Design

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
    *   [ActionDispatcher](./contexts/executor/services/action_dispatcher.md) (New)
    *   [ActionFactory](./contexts/executor/services/action_factory.md)
    *   [ContextService](./contexts/executor/services/context_service.md)
    *   [ExecutionOrchestrator](./contexts/executor/services/execution_orchestrator.md) (New)
    *   [PlanParser](./contexts/executor/services/plan_parser.md) (New)

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

## 5. Project Stages & Polar Stars

This section tracks the high-level project stages. Each stage delivers a significant set of features guided by a "Polar Star" prototype.

| Status | Stage                         | Description                                                                                                                                                          | Polar Star |
| :----: | ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------: |
|   ✅    | **Stage 01: CLI Executor**    | Delivered the core `teddy` command-line tool for plan execution. Implemented all foundational actions, the context utility, and established the YAML-based workflow. |    N/A     |
|   📝    | **Stage 02: Interactive TUI** | Create a Terminal User Interface to streamline the workflow of interacting with the AI agents, managing context, and executing plans without leaving the terminal.   | `Planned`  |
---

## 6. Architectural Notes & Technical Debt

This section captures non-blocking architectural observations and potential areas for future refactoring.

- **CLI Exit Code Philosophy:** The application exits with a non-zero code if *any* action within a plan fails. This aligns the tool with standard CI/CD practices where a non-zero exit code universally signals failure.

- **Consistent Failure Reporting:** The `CLIFormatter` handles all `FAILURE` statuses uniformly, producing a consistent, YAML-style block for the details of any failed action. This improves both human and machine readability and is the standard for all failure reporting.

- **Static Analysis vs. Dynamic Patterns:** The refactoring of `PlanService` to use a dynamic dispatch map (`{ActionType: handler_method}`) posed a challenge for `mypy`, which could not statically verify the type relationship. The issue was pragmatically resolved with a `# type: ignore` comment, capturing the common architectural trade-off between dynamic, decoupled patterns and the guarantees of static analysis.

- **CLI Interactivity & Input Strategy:** A key architectural decision separates plan input from user interaction. The `--plan-file` CLI option is the canonical way to provide a plan, reserving `stdin` exclusively for interactive I/O, such as the global `y/n` approval mechanism or the `chat_with_user` action. This prevents input conflicts and clarifies the executor's I/O model.

- **Consolidated Acceptance Test Helpers:** The module `packages/executor/tests/acceptance/helpers.py` centralizes the logic for running the `teddy` executor in tests. It provides distinct helper functions for invoking plan-based actions (`run_teddy_with_plan_structure`) and non-plan utility commands (`run_teddy_command`), establishing a clear and reusable pattern for acceptance testing.

- **Platform-Agnostic Test Data Generation:** Acceptance tests that generate YAML plans must be platform-agnostic, especially concerning file paths. The `run_teddy_with_plan_structure` helper in `tests/acceptance/helpers.py` is the required pattern. It accepts a Python data structure, recursively converts any `pathlib.Path` objects to POSIX-compliant strings, and then serializes the structure to a valid YAML plan. This centralizes platform-safe test data generation, making tests robust and cross-platform compatible.

- **Acceptance Testing for Network I/O:** For features involving network I/O (like the `research` action), mocks applied in the test runner do not affect the application running as a separate subprocess. The required pattern is "white-box" acceptance testing: the test directly instantiates the relevant application service (e.g., `PlanService`) and injects a mocked adapter. This ensures tests are fast, reliable, and do not make real network calls.

- **YAML Formatting for Readability:** The final YAML report is formatted for human readability. Multi-line strings are formatted using YAML's literal block style (`|`), achieved via a custom string representer for the `PyYAML` library.

- **Composition Root Complexity:** The composition root in `packages/executor/src/teddy_executor/main.py` is growing complex. Future work should consider introducing a formal dependency injection container or factory pattern to manage service instantiation.

- **Canonical `repotree` Format for LLMs:** The `LocalRepoTreeGenerator` produces a simple, space-indented list of files and directories. This is the canonical format for providing file hierarchy context to an LLM, as it is token-efficient, platform-agnostic, and unambiguously machine-readable, avoiding the fragility and complexity of visual tree formats.

- **Configuration Unification:** User-managed context configuration files (e.g., `perm.context`, `temp.context`) use a simple, newline-delimited `.context` format for better semantic meaning. System-generated context artifacts, such as `repotree.txt`, retain a `.txt` extension.

- **Context-Driven Output:** The `context` command's output is driven entirely by the contents of the context configuration files (`.teddy/*.context`). The command generates artifacts (like the repo tree) to files, and these files must be explicitly listed in a context file to be included in the final output, making the command's behavior explicit and configurable.

- **Context-Specific Ignores with `.teddyignore`:** To allow filtering of context for the AI without modifying the project's primary `.gitignore` file, the `LocalRepoTreeGenerator` supports a `.teddyignore` file in the project root. This file uses the same syntax as `.gitignore`. Its rules are applied with higher precedence, allowing it to override `.gitignore` rules (e.g., using `!` to re-include an ignored file). This provides a clean separation and ultimate control over the AI context versus the version control context.

- **Comment Handling in Context Files:** The parser for `.context` files intentionally ignores empty lines and any lines beginning with a `#` character. This allows for comments and spacing to be used for better readability without affecting the application's behavior.

- **Robust Acceptance Testing via Parsing:** CI failures caused by environment-specific YAML formatting have shown that asserting against raw string output is brittle. The required pattern for acceptance tests that check structured output (like the YAML report) is to first parse the output into a data structure, and then make assertions against specific fields. This makes tests resilient to cosmetic formatting changes. Future work should include a dedicated refactoring slice to apply this pattern to the entire acceptance test suite.

- **`ExecutionReport` Data Model Drift:** There is a known inconsistency in the `ExecutionReport` domain model (`run_summary`, `action_logs`) and its associated tests. The `CLIFormatter` has also been adapted to handle this by filtering out `None` values. This represents technical debt that must be addressed in a dedicated refactoring slice to unify the data model and make test assertions more consistent.

- **Acceptance Testing for CLI Commands with Mocks:** The `execute` command, which requires mocking `pyperclip`, revealed a critical testing principle. Mocks applied in the `pytest` process are not inherited by child processes launched via `subprocess`. Therefore, the required pattern for acceptance testing CLI commands that depend on mocks is **"white-box" acceptance testing using `typer.testing.CliRunner`**. This runs the CLI application logic in the same process as the test, ensuring mocks are respected. The `CliRunner` should be instantiated with `mix_stderr=False` to allow for separate inspection of `stdout` and `stderr`.
