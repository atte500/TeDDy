# System Architecture: TeDDy

This document outlines the technical standards, conventions, and setup process for the `TeDDy` project.

## 1. Conventions & Standards

### Language & Runtime
- **Language:** Python
- **Version:** 3.11+

### Dependency Management
- **Tool:** `Poetry`.
- **Usage:** Dependencies are defined in `pyproject.toml` at the project root. The `teddy_executor` package is configured as an installable CLI tool. Once installed via `poetry install`, the `teddy` command is available within the activated Poetry shell. For development tasks, commands should be run directly from the project root using `poetry run ...`.

### Version Control Strategy
- **System:** Git
- **Branching:** Trunk-Based Development on the `main` branch.
- **Commit Messages:** Must follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification.

### CI/CD Strategy
- **Platform:** GitHub Actions.
- **Triggers:** On every push to the `main` branch.
- **Pipeline:** The CI pipeline executes two parallel jobs:
    1.  **Test Suite (Blocking):** A multi-OS matrix (Ubuntu, macOS, Windows) running the full `pytest` suite. Failures here block merges.
    2.  **Quality Checks (Non-Blocking):** Runs the full `pre-commit` suite (excluding tests) on Ubuntu. Configured with `continue-on-error: true` to surface technical debt (linting, complexity, security) without halting development velocity.

### Service Layer Naming Convention
- **Dependency Attributes:** Injected dependencies in the core application services (`src/teddy_executor/core/services/`) MUST be private.
- **Rationale:** This enforces a consistent pattern across the service layer, clearly distinguishing injected dependencies from public methods or other attributes.

### Command Execution with Poetry
- **Principle:** Commands are executed from the **project root**.
- **Rule:** All file paths provided to such commands **MUST be relative to the project root**.
- **Correct Pattern:**
  ```bash
  # Correctly provides a path relative to the project root
  poetry run pytest tests/acceptance/test_prompt_action.py
  ```
- **Incorrect Pattern:**
  ```bash
  # Incorrectly assumes a different CWD; paths must always be from project root.
  poetry run pytest src/teddy_executor/tests/acceptance/test_quality_of_life_improvements.py
  ```

### Testing Strategy
- **Framework:** `pytest` with the `anyio` plugin for asynchronous testing.
- **Mocking Strategy:** This project uses the standard `unittest.mock` library (specifically the `patch` decorator and context manager) for all mocking needs.
- **Location of Tests:** Tests are organized into two primary top-level directories:
    - **`tests/suites/`**: Contains the test pyramid validating system intent.
        - `tests/suites/acceptance/`: End-to-end tests validating full user workflows.
        - `tests/suites/integration/`: Tests for components interacting with external systems.
        - `tests/suites/unit/`: Tests for individual functions or classes in isolation.
    - **`tests/harness/`**: Contains the testing infrastructure and utilities.
        - `tests/harness/setup/`: Workspace management and DI isolation.
        - `tests/harness/drivers/`: DSLs and adapters for driving the system.
        - `tests/harness/observers/`: Parsers for verifying system output.
- **Execution:** Tests are run from the **project root** using `poetry run pytest`. All asynchronous tests MUST be decorated with `@pytest.mark.anyio`.
    - **Run all tests:** `poetry run pytest` (Runs in parallel by default via `-n auto` in `pyproject.toml`)
    - **Run all tests with coverage:** `poetry run pytest --cov=src --cov-report=term-missing`
    - **Run all tests (Force Sequential):** `poetry run pytest -n 0`
    - **Run tests in a specific file:** `poetry run pytest tests/acceptance/test_prompt_action.py`
    - **Run a specific test by name:** `poetry run pytest -k "test_prompt_gets_response"`
- **Test Coverage:** Test coverage standards are enforced as part of the CI Quality Gates.

### Pre-commit Hooks
- **Goal:** To provide a fast, local feedback loop for developers.
- **Framework:** `pre-commit`, configured in `.pre-commit-config.yaml`.
- **Principle:** Pre-commit hooks MUST be scoped strictly to **staged files** to provide a fast, local feedback loop. Heavy, repository-wide checks (like the full test suite, copy-paste detection, or test pyramid verification) belong in the Continuous Integration (CI) pipeline, not on the developer's local machine pre-commit.
- **Included Checks:**
    -   **Quality Gate:**
        - `ruff-complexity`: Enforces a **precise Cyclomatic Complexity** limit of **9** per function (Rule `C901`) and a **precise Statement Limit** of **40** per function (Rule `PLR0915`) for ALL code.
        - `file-length-python`: Enforces a strict **300 line limit** for all Python files (excluding `spikes/` and `prototypes/`). The check reports the actual file length on failure for quick assessment.
    - **Style & Formatting:**
        - `ruff`: For linting and formatting. **Note:** `E501` (Line too long) is explicitly ignored to favor readability of long URLs and comments.
    - **Correctness:**
        - `mypy`: For static type checking.
        - `vulture`: For dead code detection.
    - **Security:**
        - `detect-secrets`: For hardcoded credential prevention.
        - `bandit`: For static security analysis.
        - `pip-audit`: Vulnerability scanning (runs only when dependency files change).
    - **Sanity & Consistency:**
        - `check-yaml`, `check-toml`, and other basic file checks.

### CI Quality Gates
- **Goal:** To provide a comprehensive, automated quality gate that protects the main branch.
- **Principle:** The CI pipeline runs checks in two categories:
    1. The full `pre-commit` suite (using `--all-files`) to verify global compatibility and system health.
    2. Slower, repository-wide checks that are not suitable for local pre-commit hooks, such as Test Pyramid verification and copy-paste detection. These checks MUST exclude experimental directories like `prototypes/` and `spikes/`.

### Experimental Code Exclusion
The `spikes/` and `prototypes/` directories are intentionally excluded from all quality gates (`ruff`, `mypy`, `vulture`, `jscpd`, etc.).
- **Rationale:** These directories are for rapid, isolated experimentation. The code within them is temporary and not expected to meet production quality standards. Enforcing linting and other checks would hinder their exploratory purpose.

### Handling of Secrets
- **Scanning:** Managed via `detect-secrets`.
- **False Positives:** MUST be handled by updating `.secrets.baseline`. **Do not use inline pragmas.**

### Configuration Hierarchy
- **Principle:** The system follows a "Safe-by-Default" configuration strategy.
- **Hierarchy:**
    1. **Active Config:** `.teddy/config.yaml` (Personal overrides, not committed).
    2. **Project Template:** `config/config.yaml` (Reference defaults, committed).
    3. **Hardcoded Fallbacks:** Defined within the services (e.g., `ActionFactory`, `PlanValidator`).
- **Guideline:** Services MUST provide hardcoded fallbacks to the `IConfigService.get_setting` method to ensure stability in uninitialized environments.

### Third-Party Dependency Vetting
- **Strategy:** Mandate a "Verify, Then Document" Spike for new dependencies.
- **Rationale:** Based on the RCA for a failure involving the `gitwalk` library ([see RCA](./rca/unreliable-third-party-library-gitwalk.md)), new third-party dependencies must be de-risked before integration.
- **Process:** Before a new dependency is used, a minimal technical spike must prove its core functionality. The successful spike script should be referenced in the final adapter design document.

---

## 2. Component & Boundary Map

This section serves as both the strategic **Boundary Map** and the detailed **Component Map** for the system.

**Boundary Analysis:** The `teddy_executor` follows a Hexagonal Architecture. The boundary separates the core business logic (domain models, services, and ports) from the platform-specific integration layer (the CLI) and infrastructure (the local filesystem, shell, and web). **Primary Adapters** act as the explicit translation layer across this boundary, ensuring the core remains isolated and independently testable.

### `teddy_executor` Package

#### Hexagonal Core

| Component                    | Description                                                                                                                                         | Contract                                                                       |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| **Domain Model**             | Defines the core entities, value objects, and ubiquitous language of the application.                                                               | [Domain Model & Ubiquous Language](./core/domain_model.md)                     |
| **ExecutionReport**          | A strongly-typed, immutable data structure representing the outcome of a plan execution.                                                            | [ExecutionReport](./core/domain/execution_report.md)                           |
| **ShellOutput**              | A strictly-typed DTO representing the result of a shell command execution.                                                                          | [ShellOutput](./core/domain/shell_output.md)                                   |
| **WebSearchResults**         | A strictly-typed DTO representing the aggregated results from a web search.                                                                         | [WebSearchResults](./core/domain/web_search_results.md)                        |
| **ProjectContext**           | A strictly-typed DTO representing the aggregated project context for display.                                                                       | [ProjectContext](./core/domain/project_context.md)                             |
| **IGetContextUseCase**       | Defines the inbound port for orchestrating the collection of project context.                                                                       | [IGetContextUseCase](./core/ports/inbound/get_context_use_case.md)             |
| **IInitUseCase**             | Defines the inbound port for project auto-initialization.                                                                                           | [IInitUseCase](./core/ports/inbound/init.md)                                   |
| **IRunPlanUseCase**          | Defines the primary inbound port for executing a plan from a raw YAML string.                                                                       | [IRunPlanUseCase](./core/ports/inbound/run_plan_use_case.md)                   |
| **IPlanningUseCase**         | Defines the inbound port for generating a plan from a user message.                                                                                 | [IPlanningUseCase](./core/ports/inbound/planning_use_case.md)                  |
| **IPlanReviewer**            | Defines the inbound port for the interactive review and modification of a plan.                                                                     | [IPlanReviewer](./core/ports/inbound/plan_reviewer.md)                         |
| **IPlanParser**              | Defines the inbound port for parsing a plan from a raw string into a `Plan` object.                                                                 | [IPlanParser](./core/ports/inbound/plan_parser.md)                             |
| **IPlanValidator**           | Defines the inbound port for performing pre-flight validation of a `Plan` object.                                                                   | [IPlanValidator](./core/ports/inbound/plan_validator.md)                       |
| **IPlanReviewer**            | Defines the inbound port for the interactive review and modification of a plan.                                                                     | [IPlanReviewer](./core/ports/inbound/plan_reviewer.md)                         |
| **IConfigService**           | Defines the outbound port for retrieving application configuration and secrets.                                                                     | [IConfigService](./core/ports/outbound/config_service.md)                      |
| **IEnvironmentInspector**    | Defines the outbound port for gathering information about the host operating environment.                                                           | [IEnvironmentInspector](./core/ports/outbound/environment_inspector.md)        |
| **IFileSystemManager**       | Defines a technology-agnostic outbound port for all file system operations (create, read, edit).                                                    | [IFileSystemManager](./core/ports/outbound/file_system_manager.md)             |
| **ILlmClient**               | Defines the outbound port for communicating with a Large Language Model.                                                                            | [ILlmClient](./core/ports/outbound/llm_client.md)                              |
| **IMarkdownReportFormatter** | Defines the outbound port for formatting an `ExecutionReport` into a Markdown string.                                                               | [IMarkdownReportFormatter](./core/ports/outbound/markdown_report_formatter.md) |
| **IRepoTreeGenerator**       | Defines the outbound port for generating a file tree, respecting `.gitignore` and `.teddyignore` files.                                             | [IRepoTreeGenerator](./core/ports/outbound/repo_tree_generator.md)             |
| **IShellExecutor**           | Defines the outbound port for executing shell commands and returning a `ShellOutput` DTO.                                                           | [IShellExecutor](./core/ports/outbound/shell_executor.md)                      |
| **IUserInteractor**          | Defines the outbound port for prompting the user for confirmation and free-text input.                                                              | [IUserInteractor](./core/ports/outbound/user_interactor.md)                    |
| **IWebScraper**              | Defines the outbound port for fetching and converting remote web page content to Markdown.                                                          | [IWebScraper](./core/ports/outbound/web_scraper.md)                            |
| **IWebSearcher**             | Defines the outbound port for performing web searches and returning structured results.                                                             | [IWebSearcher](./core/ports/outbound/web_searcher.md)                          |
| **ActionDispatcher**         | A service that resolves and executes a single action, delegating to the `ActionFactory`.                                                            | [ActionDispatcher](./core/services/action_dispatcher.md)                       |
| **ActionFactory**            | A factory service that creates validated `Action` domain objects from raw plan data.                                                                | [ActionFactory](./core/services/action_factory.md)                             |
| **EditSimulator**            | A pure service for applying a sequence of FIND/REPLACE edits to a string in memory.                                                                 | [EditSimulator](./core/services/edit_simulator.md)                             |
| **ContextService**           | The service that implements `IGetContextUseCase` by orchestrating outbound ports to gather and format project context.                              | [ContextService](./core/services/context_service.md)                           |
| **ExecutionOrchestrator**    | The primary service that implements `IRunPlanUseCase`, managing the step-by-step execution of a parsed `Plan` object.                               | [ExecutionOrchestrator](./core/services/execution_orchestrator.md)             |
| **InitService**              | The service that implements `IInitUseCase`, ensuring projects are initialized before command execution. Supports a configurable template directory. | [InitService](./core/services/init_service.md)                                 |
| **PlanningService**          | Orchestrates context gathering and LLM interaction to generate plans.                                                                               | [PlanningService](./core/services/planning_service.md)                         |
| **SessionService**           | Manages the filesystem structure and machine-readable metadata for TeDDy sessions.                                                                  | [SessionService](./core/services/session_service.md)                           |
| **SessionOrchestrator**      | A wrapper service implementing the "Turn Transition Algorithm" and "Auto-Naming" logic.                                                             | [SessionOrchestrator](./core/services/session_orchestrator.md)                 |
| **MarkdownPlanParser**       | A service that parses a Markdown plan string into a `Plan` domain object using a strict, single-pass AST traversal.                                 | [MarkdownPlanParser](./core/services/markdown_plan_parser.md)                  |
| **Action Parser Strategies** | A set of strategy functions for parsing specific action types within a plan.                                                                        | [ActionParserStrategies](./core/services/action_parser_strategies.md)          |
| **Parser Metadata**          | Specialized logic for extracting parameters from metadata lists and messages during plan parsing.                                                   | [ParserMetadata](./core/services/parser_metadata.md)                           |
| **Parser Infrastructure**    | Low-level utilities for AST traversal, stream management, and path normalization used during plan parsing.                                          | [ParserInfrastructure](./core/services/parser_infrastructure.md)               |
| **MarkdownReportFormatter**  | Implements `IMarkdownReportFormatter` using the Jinja2 template engine to generate CLI reports.                                                     | [MarkdownReportFormatter](./core/services/markdown_report_formatter.md)        |
| **PlanValidator**            | Implements `IPlanValidator` using a strategy pattern to run pre-flight checks on a plan's actions.                                                  | [PlanValidator](./core/services/plan_validator.md)                             |

#### Primary Adapters

| Component                      | Description                                                                                                          | Contract                                                                          |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| **CLI Adapter**                | The primary inbound adapter that drives the application via the `Typer` CLI framework.                               | [CLI Adapter](./adapters/inbound/cli.md)                                          |
| **TextualPlanReviewer**        | Implements `IPlanReviewer` using a dual-pane `Textual` TUI (ActionTree/ParameterDetail) for interactive plan review. | [TextualPlanReviewer](./adapters/inbound/textual_plan_reviewer.md)                |
| **ConsoleInteractor**          | Implements `IUserInteractor` for the console, providing diff previews for file operations.                           | [ConsoleInteractorAdapter](./adapters/outbound/console_interactor.md)             |
| **ConsoleTooling**             | A utility for centralized discovery of editors and diff viewers, respecting configuration and system environment.    | [ConsoleTooling](./adapters/outbound/console_tooling.md)                          |
| **LiteLLMAdapter**             | Implements `ILlmClient` using the `litellm` library for multi-provider LLM communication.                            | [LiteLLMAdapter](./adapters/outbound/litellm_adapter.md)                          |
| **LocalFileSystemAdapter**     | Implements `IFileSystemManager` for the local disk using Python's `pathlib`.                                         | [LocalFileSystemAdapter](./adapters/outbound/local_file_system_adapter.md)        |
| **LocalRepoTreeGenerator**     | Implements `IRepoTreeGenerator` using the `pathspec` library to handle ignore files.                                 | [LocalRepoTreeGenerator](./adapters/outbound/local_repo_tree_generator.md)        |
| **ShellAdapter**               | Implements `IShellExecutor` using Python's `subprocess` module.                                                      | [ShellAdapter](./adapters/outbound/shell_adapter.md)                              |
| **SystemEnvironmentInspector** | Implements `IEnvironmentInspector` using Python's `os`, `platform`, and `sys` modules.                               | [SystemEnvironmentInspector](./adapters/outbound/system_environment_inspector.md) |
| **WebScraperAdapter**          | Implements `IWebScraper` using `trafilatura` for content extraction and a direct-fetch for GitHub URLs.              | [WebScraperAdapter](./adapters/outbound/web_scraper_adapter.md)                   |
| **WebSearcherAdapter**         | Implements `IWebSearcher` using the `ddgs` library for keyless DuckDuckGo searches.                                  | [WebSearcherAdapter](./adapters/outbound/web_searcher_adapter.md)                 |
| **YamlConfigAdapter**          | Implements `IConfigService` by reading configuration from a `.teddy/config.yaml` file.                               | [YamlConfigAdapter](./adapters/outbound/yaml_config_adapter.md)                   |

#### Test Harness Triad (Setup, Driver, Observer)

| Component                        | Description                                                                                                                                | Contract                                               |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------ |
| **MarkdownPlanBuilder** (Driver) | A fluent DSL for constructing validated Markdown plans. MUST be used in tests to generate plan strings instead of hardcoding raw Markdown. | [MarkdownPlanBuilder](./tests/drivers/plan_builder.md) |
| **ReportParser** (Observer)      | An "Inverse Adapter" that parses Markdown reports back into structured DTOs for assertions.                                                | [ReportParser](./tests/observers/report_parser.md)     |
| **CliTestAdapter** (Driver)      | A specialized adapter that drives the CLI in-process and orchestrates builders and parsers.                                                | [CliTestAdapter](./tests/drivers/cli_adapter.md)       |
| **TestEnvironment** (Setup)      | A harness that encapsulates DI isolation, environment patching, and workspace management.                                                  | [TestEnvironment](./tests/setup/test_environment.md)   |
| **TestComposition (Fixtures)**   | A set of reusable pytest fixtures and globally mocked heavy dependencies (e.g., LiteLLM).                                                  | [TestComposition](./tests/setup/composition.md)        |

---

## 3. Key Architectural Decisions

This section serves as the "System Law" (Poka-Yoke) for TeDDy. It defines the prescriptive standards that all development work MUST follow.

- **Test Harness:** Reside exclusively in `tests/`. (Ensures strict isolation between production and test code.)
- **Temp Files:** Create in `tests/.tmp/` and clean up during teardown. (Prevents filesystem pollution and simplifies CI management.)
- **Global Config:** Unify in `tests/conftest.py` exporting from `tests/harness/setup/composition.py`. (Maintains a clean Primary Driving Adapter layer.)
- **Architecture:** Use Hexagonal Architecture (Ports & Adapters). (Enables independent testing and technology swapping.)
- **DI Implementation:** Use the `punq` library. (Decouples services from concrete implementations.)
- **DI Testing:** All tests requiring DI MUST use the centralized `container` fixture. (Ensures isolation and correct patching.)
- **DI Scopes:** Use `punq.Scope.transient` for services and adapters. (Prevents state leakage across CLI turns or tests.)
- **Acceptance Testing:** Use `typer.testing.CliRunner` for in-process execution. (Ensures speed, reliability, and mock respect.)
- **Type Enforcement:** Rely on static checking (Mypy) in pre-commit; do not enforce at runtime. (Balances safety with low overhead.)
- **Structured Output:** Parse output into data structures before assertion. (Ensures resilience to minor formatting changes.)
- **CLI I/O:** Use positional arguments for files; reserve `stdin` for prompts. (Prevents input stream conflicts.)
- **Execution Testing:** Use `--plan-content` with `MarkdownPlanBuilder`. (Maintains protocol validity and test readability.)
- **Execute Action:** Allow shell chaining and inline directives. (Simplifies protocol and maintains statelessness.)
- **Windows Failure:** Use `cmd /c` to isolate terminating commands. (Ensures parent process can report failures.)
- **Reporting:** Use Jinja2 Macros for modularity. (Ensures consistency and facilitates section extraction.)
- **Encoding:** Explicitly specify `utf-8` for all file operations. (Ensures predictable platform-agnostic behavior.)
- **Serialization:** Enforce strict primitive validation before serialization. (Prevents infinite recursion or hangs from dynamic objects.)
- **Initialization:** Import heavy libraries (`litellm`, `trafilatura`) lazily. (Ensures CLI initializes under 500ms.)
- **Binary Stability:** Abstract heavy binary libs into private getters and mock the getter. (Prevents worker crashes in distributed tests.)
- **Validation:** Optimize plan rules for performance on large inputs. (Ensures low-latency feedback loops.)
- **Sequence Matching:** Use tiered heuristics with Priority Capping. (Balances AI resilience with sub-second performance.)
- **TUI Responsiveness:** Decorate modal/external tool handlers with `@work`. (Prevents UI deadlocks.)
- **TUI Editing:** Use Non-Blocking Deferred Harvest for external editors. (Maintains TUI responsiveness during editing.)
- **TUI Test Speed:** Use `TuiDriver.set_input` or direct assignment. (~50x faster than character-by-character simulation.)
- **Pre-commit Workflow:** Scope local checks strictly to staged files. (Ensures fast feedback loops while delegating global checks to CI.)


---

## 4. Debug Mode

To aid in fault isolation, the `teddy` executor includes a debug mode that can be activated via an environment variable.

-   **Activation:** Set the `TEDDY_DEBUG` environment variable to any non-empty value (e.g., `export TEDDY_DEBUG=true`).
-   **Behavior:** When active, this mode enables detailed logging for specific, hard-to-diagnose components.
    -   **`MarkdownPlanParser`:** Prints a detailed Abstract Syntax Tree (AST) of the parsed plan to standard output. This is crucial for debugging parsing logic and issues related to Markdown structure.
