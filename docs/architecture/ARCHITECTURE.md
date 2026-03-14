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
- **Pipeline:** The CI pipeline will lint, type-check, test, and build the packages.

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
- **Framework:** `pytest`.
- **Location of Tests:** Tests are organized as follows:
    - `tests/acceptance/`: End-to-end tests validating full user workflows. These should be kept to a minimum to maintain suite execution speed.
    - `tests/integration/`: Tests for components interacting with external systems AND high-level orchestration/service tests that do not require full end-to-end setup.
    - `tests/unit/`: Tests for individual functions or classes in isolation.
- **Execution:** Tests are run from the **project root** using `poetry run pytest`.
    - **Run all tests:** `poetry run pytest` (Runs in parallel by default via `-n auto` in `pyproject.toml`)
    - **Run all tests with coverage:** `poetry run pytest --cov=src --cov-report=term-missing`
    - **Run all tests (Force Sequential):** `poetry run pytest -n 0`
    - **Run tests in a specific file:** `poetry run pytest tests/acceptance/test_prompt_action.py`
    - **Run a specific test by name:** `poetry run pytest -k "test_prompt_gets_response"`
- **Test Coverage:** Test coverage standards are enforced as part of the CI Quality Gates.

### Pre-commit Hooks
- **Goal:** To provide a fast, local feedback loop for developers.
- **Framework:** `pre-commit`, configured in `.pre-commit-config.yaml`.
- **Principle:** All hooks configured here **must** be fast to run.
- **Included Checks:**
    - **Style & Formatting:**
        - `ruff`: For linting and formatting. **Note:** `E501` (Line too long) is explicitly ignored to favor readability of long URLs and comments.
    - **Correctness:**
        - `mypy`: For static type checking.
    - **Sanity & Consistency:**
        - `check-yaml`, `check-toml`, and other basic file checks.

### CI Quality Gates
- **Goal:** To provide a comprehensive, automated quality gate that protects the main branch.
- **Principle:** The CI pipeline **must** run all checks from the `pre-commit` suite. It **may** also include additional, slower-running checks.
- **CI-Only Checks:**
    - **Test Coverage:** The CI pipeline **must** perform test coverage analysis using `pytest-cov` and enforce a strict failure threshold of **90%**. Note: Coverage is disabled by default for local runs to optimize the developer "Inner Loop" speed; it must be explicitly invoked or run via CI.
    - **Code Duplication:** Checked via `jscpd` with a minimum token count of **50**.
    - **Complexity & Dead Code:**
        - `ruff`: Configured to enforce a **precise Cyclomatic Complexity** limit of **9** per function (Rule `C901`) and a **precise Statement Limit** of **40** per function (Rule `PLR0915`).
        - `vulture`: For detecting dead (unreachable) code. Must be configured with a minimum confidence of **80%**.
        - **File Length (SLOC):** A custom check enforces a maximum of **300 lines** per Python file (excluding tests and spikes). This ensures components remain focused and modular.

### Spike Directory Exclusion
The `spikes/` directory is intentionally excluded from `ruff` and `mypy` checks in `.pre-commit-config.yaml`.
- **Rationale:** Spikes are for rapid, isolated experimentation. The code within them is temporary and not expected to meet production quality standards. Enforcing linting would hinder their exploratory purpose.

### Handling of Secrets
- **Scanning:** Managed via `detect-secrets`.
- **False Positives:** MUST be handled by updating `.secrets.baseline`. **Do not use inline pragmas.**

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

| Component                    | Description                                                                                                            | Contract                                                                       |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| **Domain Model**             | Defines the core entities, value objects, and ubiquitous language of the application.                                  | [Domain Model & Ubiquous Language](./core/domain_model.md)                     |
| **ExecutionReport**          | A strongly-typed, immutable data structure representing the outcome of a plan execution.                               | [ExecutionReport](./core/domain/execution_report.md)                           |
| **ShellOutput**              | A strictly-typed DTO representing the result of a shell command execution.                                             | [ShellOutput](./core/domain/shell_output.md)                                   |
| **WebSearchResults**         | A strictly-typed DTO representing the aggregated results from a web search.                                            | [WebSearchResults](./core/domain/web_search_results.md)                        |
| **ProjectContext**           | A strictly-typed DTO representing the aggregated project context for display.                                          | [ProjectContext](./core/domain/project_context.md)                             |
| **IGetContextUseCase**       | Defines the inbound port for orchestrating the collection of project context.                                          | [IGetContextUseCase](./core/ports/inbound/get_context_use_case.md)             |
| **IInitUseCase**             | Defines the inbound port for project auto-initialization.                                                              | [IInitUseCase](./core/ports/inbound/init.md)                                   |
| **IRunPlanUseCase**          | Defines the primary inbound port for executing a plan from a raw YAML string.                                          | [IRunPlanUseCase](./core/ports/inbound/run_plan_use_case.md)                   |
| **IPlanningUseCase**         | Defines the inbound port for generating a plan from a user message.                                                    | [IPlanningUseCase](./core/ports/inbound/planning_use_case.md)                  |
| **IPlanReviewer**            | Defines the inbound port for the interactive review and modification of a plan.                                        | [IPlanReviewer](./core/ports/inbound/plan_reviewer.md)                         |
| **IPlanParser**              | Defines the inbound port for parsing a plan from a raw string into a `Plan` object.                                    | [IPlanParser](./core/ports/inbound/plan_parser.md)                             |
| **IPlanValidator**           | Defines the inbound port for performing pre-flight validation of a `Plan` object.                                      | [IPlanValidator](./core/ports/inbound/plan_validator.md)                       |
| **IPlanReviewer**            | Defines the inbound port for the interactive review and modification of a plan.                                        | [IPlanReviewer](./core/ports/inbound/plan_reviewer.md)                         |
| **IConfigService**           | Defines the outbound port for retrieving application configuration and secrets.                                        | [IConfigService](./core/ports/outbound/config_service.md)                      |
| **IEnvironmentInspector**    | Defines the outbound port for gathering information about the host operating environment.                              | [IEnvironmentInspector](./core/ports/outbound/environment_inspector.md)        |
| **IFileSystemManager**       | Defines a technology-agnostic outbound port for all file system operations (create, read, edit).                       | [IFileSystemManager](./core/ports/outbound/file_system_manager.md)             |
| **ILlmClient**               | Defines the outbound port for communicating with a Large Language Model.                                               | [ILlmClient](./core/ports/outbound/llm_client.md)                              |
| **IMarkdownReportFormatter** | Defines the outbound port for formatting an `ExecutionReport` into a Markdown string.                                  | [IMarkdownReportFormatter](./core/ports/outbound/markdown_report_formatter.md) |
| **IRepoTreeGenerator**       | Defines the outbound port for generating a file tree, respecting `.gitignore` and `.teddyignore` files.                | [IRepoTreeGenerator](./core/ports/outbound/repo_tree_generator.md)             |
| **IShellExecutor**           | Defines the outbound port for executing shell commands and returning a `ShellOutput` DTO.                              | [IShellExecutor](./core/ports/outbound/shell_executor.md)                      |
| **IUserInteractor**          | Defines the outbound port for prompting the user for confirmation and free-text input.                                 | [IUserInteractor](./core/ports/outbound/user_interactor.md)                    |
| **IWebScraper**              | Defines the outbound port for fetching and converting remote web page content to Markdown.                             | [IWebScraper](./core/ports/outbound/web_scraper.md)                            |
| **IWebSearcher**             | Defines the outbound port for performing web searches and returning structured results.                                | [IWebSearcher](./core/ports/outbound/web_searcher.md)                          |
| **ActionDispatcher**         | A service that resolves and executes a single action, delegating to the `ActionFactory`.                               | [ActionDispatcher](./core/services/action_dispatcher.md)                       |
| **ActionFactory**            | A factory service that creates validated `Action` domain objects from raw plan data.                                   | [ActionFactory](./core/services/action_factory.md)                             |
| **EditSimulator**            | A pure service for applying a sequence of FIND/REPLACE edits to a string in memory.                                    | [EditSimulator](./core/services/edit_simulator.md)                             |
| **ContextService**           | The service that implements `IGetContextUseCase` by orchestrating outbound ports to gather and format project context. | [ContextService](./core/services/context_service.md)                           |
| **ExecutionOrchestrator**    | The primary service that implements `IRunPlanUseCase`, managing the step-by-step execution of a parsed `Plan` object and enforcing terminal action isolation. | [ExecutionOrchestrator](./core/services/execution_orchestrator.md)             |
| **InitService**              | The service that implements `IInitUseCase`, ensuring projects are initialized before command execution.                | [InitService](./core/services/init_service.md)                                 |
| **PlanningService**          | Orchestrates context gathering and LLM interaction to generate plans.                                                  | [PlanningService](./core/services/planning_service.md)                         |
| **SessionService**           | Manages the filesystem structure and machine-readable metadata for TeDDy sessions.                                     | [SessionService](./core/services/session_service.md)                           |
| **SessionOrchestrator**      | A wrapper service implementing the "Turn Transition Algorithm" and "Auto-Naming" logic.                               | [SessionOrchestrator](./core/services/session_orchestrator.md)                 |
| **MarkdownPlanParser**       | A service that parses a Markdown plan string into a `Plan` domain object using a strict, single-pass AST traversal.    | [MarkdownPlanParser](./core/services/markdown_plan_parser.md)                  |
| **Action Parser Strategies** | A set of strategy functions for parsing specific action types within a plan.                                           | [ActionParserStrategies](./core/services/action_parser_strategies.md)          |
| **Parser Metadata**          | Specialized logic for extracting parameters from metadata lists and messages during plan parsing.                      | [ParserMetadata](./core/services/parser_metadata.md)                           |
| **Parser Infrastructure**    | Low-level utilities for AST traversal, stream management, and path normalization used during plan parsing.             | [ParserInfrastructure](./core/services/parser_infrastructure.md)               |
| **MarkdownReportFormatter**  | Implements `IMarkdownReportFormatter` using the Jinja2 template engine to generate CLI reports.                        | [MarkdownReportFormatter](./core/services/markdown_report_formatter.md)        |
| **PlanValidator**            | Implements `IPlanValidator` using a strategy pattern to run pre-flight checks on a plan's actions.                     | [PlanValidator](./core/services/plan_validator.md)                             |

#### Primary Adapters

| Component                      | Description                                                                                             | Contract                                                                          |
| ------------------------------ | ------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| **CLI Adapter**                | The primary inbound adapter that drives the application via the `Typer` CLI framework.                  | [CLI Adapter](./adapters/inbound/cli.md)                                          |
| **TextualPlanReviewer**        | Implements `IPlanReviewer` using the `Textual` TUI framework for interactive plan review.               | [TextualPlanReviewer](./adapters/inbound/textual_plan_reviewer.md)                |
| **ConsoleInteractor**          | Implements `IUserInteractor` for the console, providing diff previews for file operations.              | [ConsoleInteractorAdapter](./adapters/outbound/console_interactor.md)             |
| **LiteLLMAdapter**             | Implements `ILlmClient` using the `litellm` library for multi-provider LLM communication.               | [LiteLLMAdapter](./adapters/outbound/litellm_adapter.md)                          |
| **LocalFileSystemAdapter**     | Implements `IFileSystemManager` for the local disk using Python's `pathlib`.                            | [LocalFileSystemAdapter](./adapters/outbound/local_file_system_adapter.md)        |
| **LocalRepoTreeGenerator**     | Implements `IRepoTreeGenerator` using the `pathspec` library to handle ignore files.                    | [LocalRepoTreeGenerator](./adapters/outbound/local_repo_tree_generator.md)        |
| **ShellAdapter**               | Implements `IShellExecutor` using Python's `subprocess` module.                                         | [ShellAdapter](./adapters/outbound/shell_adapter.md)                              |
| **SystemEnvironmentInspector** | Implements `IEnvironmentInspector` using Python's `os`, `platform`, and `sys` modules.                  | [SystemEnvironmentInspector](./adapters/outbound/system_environment_inspector.md) |
| **WebScraperAdapter**          | Implements `IWebScraper` using `trafilatura` for content extraction and a direct-fetch for GitHub URLs. | [WebScraperAdapter](./adapters/outbound/web_scraper_adapter.md)                   |
| **WebSearcherAdapter**         | Implements `IWebSearcher` using the `ddgs` library for keyless DuckDuckGo searches.                     | [WebSearcherAdapter](./adapters/outbound/web_searcher_adapter.md)                 |
| **YamlConfigAdapter**          | Implements `IConfigService` by reading configuration from a `.teddy/config.yaml` file.                  | [YamlConfigAdapter](./adapters/outbound/yaml_config_adapter.md)                   |

---

## 3. Key Architectural Decisions

This section serves as the "System Law" (Poka-Yoke) for TeDDy. It defines the prescriptive standards that all development work MUST follow.

-   **Rule:** Use Hexagonal Architecture (Ports & Adapters) to isolate core business logic from external frameworks and I/O. **Rationale:** To enable independent testing and allow for easy swapping of infrastructure technologies.
-   **Rule:** Use the `punq` library for Dependency Injection in the `main.py` composition root. **Rationale:** To decouple services from concrete implementations, facilitating testability and modularity.
-   **Rule:** All tests requiring a Dependency Injection container MUST use the centralized `container` fixture in `tests/conftest.py`. **Rationale:** To ensure test isolation, reduce setup boilerplate, and correctly patch the global container used by the CLI. **Note:** This fixture must replace the entire global container instance with a fresh one to bypass `punq`'s type-locking behavior.
-   **Rule:** Orchestration, planning, service, and infrastructure adapter classes MUST be registered with `punq.Scope.transient`. **Rationale:** To prevent state leakage and ensure that services always use the most recently registered dependencies. This is critical in CLI tools where the environment (root directory) can change via bootstrapping or in sequential test runs where mocks must be isolated.
-   **Rule:** Use `typer.testing.CliRunner` to execute acceptance tests in-process. **Rationale:** This pattern is faster than `subprocess`, more reliable, and ensures that mocks are correctly respected during test execution.
-   **Rule:** Rely on static type checking via `mypy` for contract enforcement; do not enforce type hints at runtime. **Rationale:** Static analysis as a mandatory pre-commit hook provides sufficient safety without the overhead and complexity of runtime validation.
-   **Rule:** Acceptance tests verifying structured output (e.g., YAML) MUST parse the output into a data structure before assertion. **Rationale:** To make tests resilient to minor formatting changes that don't affect the data payload.
-   **Rule:** Use positional arguments for file I/O and reserve `stdin` exclusively for interactive user prompts. **Rationale:** To prevent conflicts between reading plan data and receiving user confirmation or free-text input.
-   **Rule:** Use the `--plan-content` option in the `execute` command for providing plans within acceptance tests. **Rationale:** To make tests more robust and self-contained by avoiding dependencies on the system clipboard or external files.
-   **Rule:** The `EXECUTE` action allows shell chaining and inline directives. **Rationale:** To simplify the protocol and shift responsibility for clean commands to the agent's prompting. This adheres to the "small, sharp tools" philosophy while maintaining statelessness between blocks.
-   **Rule:** Use Jinja2 Macros for modular reporting. **Rationale:** To ensure consistency across different report formats (Concise CLI vs. Session) and facilitate robust extraction of specific sections (e.g., Action Log) for aggregated views.
-   **Rule:** Explicitly specify `encoding="utf-8"` for all operations that read from or write to text files. **Rationale:** To ensure predictable, platform-agnostic behavior across different operating systems and avoid encoding errors when handling non-ASCII characters.
-   **Rule:** Domain boundaries MUST enforce strict primitive validation and casting before serialization operations (e.g., `yaml.dump`). **Rationale:** To prevent dynamic objects (like `MagicMock` in unit tests) from leaking into infrastructure adapters, preventing infinite recursion or silent hangs during serialization.
-   **Rule:** Heavy third-party libraries (e.g., `litellm`, `trafilatura`) MUST be imported lazily within the methods where they are used. **Rationale:** To ensure the CLI remains responsive and initializes in under 500ms (excluding shell overhead). Module-level imports of heavy libraries significantly degrade the user experience.
-   **Rule:** Validation rules for plan actions MUST be optimized for performance on large inputs (e.g., 500+ line prompt files). **Rationale:** To prevent high-latency feedback loops during plan pre-flight checks. Any diagnostic logic involving sequence matching (like fuzzy `EDIT` matching) MUST use tiered heuristics (Exact Anchors -> Incremental Fuzzy -> Sub-sampling) to maintain sub-second response times.

---

## 4. Debug Mode

To aid in fault isolation, the `teddy` executor includes a debug mode that can be activated via an environment variable.

-   **Activation:** Set the `TEDDY_DEBUG` environment variable to any non-empty value (e.g., `export TEDDY_DEBUG=true`).
-   **Behavior:** When active, this mode enables detailed logging for specific, hard-to-diagnose components.
    -   **`MarkdownPlanParser`:** Prints a detailed Abstract Syntax Tree (AST) of the parsed plan to standard output. This is crucial for debugging parsing logic and issues related to Markdown structure.
