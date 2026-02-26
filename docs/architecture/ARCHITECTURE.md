# System Architecture: TeDDy

This document outlines the technical standards, conventions, and setup process for the `TeDDy` project.

## 1. Conventions & Standards

### Language & Runtime
- **Language:** Python
- **Version:** 3.9+

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
  poetry run pytest tests/acceptance/test_chat_with_user_action.py
  ```
- **Incorrect Pattern:**
  ```bash
  # Incorrectly assumes a different CWD; paths must always be from project root.
  poetry run pytest src/teddy_executor/tests/acceptance/test_quality_of_life_improvements.py
  ```

### Testing Strategy
- **Framework:** `pytest`.
- **Location of Tests:** Tests are organized as follows:
    - `tests/acceptance/`: End-to-end tests.
    - `tests/integration/`: Tests for components that interact with external systems.
    - `tests/unit/`: Tests for individual functions or classes in isolation.
- **Execution:** Tests are run from the **project root** using `poetry run pytest`.
    - **Run all tests:** `poetry run pytest`
    - **Run tests in a specific file:** `poetry run pytest tests/acceptance/test_chat_with_user_action.py`
    - **Run a specific test by name:** `poetry run pytest -k "test_chat_with_user_gets_response"`
- **Test Coverage:** The CI pipeline **must** perform test coverage analysis using `pytest-cov`. It **must** be configured to fail if test coverage drops below a project-defined threshold of **90%**.

### Pre-commit Hooks & CI Quality Gates
- **Framework:** `pre-commit`.
- **Configuration:** Stored in `.pre-commit-config.yaml` at the repository root.
- **Principle:** The CI pipeline **must** execute the exact same suite of checks as the pre-commit hooks to guarantee the trunk remains clean. All hooks **must** be fast.
- **Included Hooks:**
    - **Style & Formatting:**
        - `ruff`: For linting and formatting. **Note:** `E501` (Line too long) is explicitly ignored to favor readability of long URLs and comments.
    - **Correctness:**
        - `mypy`: For static type checking.
    - **Complexity & Dead Code:**
        - `ruff`: Configured to enforce a **precise Cyclomatic Complexity** limit of **9** per function (Rule `C901`) and a **precise Statement Limit** of **40** per function (Rule `PLR0915`).
        - `vulture`: For detecting dead (unreachable) code. Must be configured with a minimum confidence of **80%**.
        - **File Length (SLOC):** A custom check enforces a maximum of **300 lines** per Python file (excluding tests and spikes). This ensures components remain focused and modular.
    - **Sanity & Consistency:**
        - `check-yaml`, `check-toml`: For syntax validation.

### Spike Directory Exclusion
The `spikes/` directory is intentionally excluded from `ruff` and `mypy` checks in `.pre-commit-config.yaml`.
- **Rationale:** Spikes are for rapid, isolated experimentation. The code within them is temporary and not expected to meet production quality standards. Enforcing linting would hinder their exploratory purpose.

### Handling of Secrets
- **Strategy:** Not applicable for this tool. If third-party API keys are needed in the future, they will be managed through environment variables.

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

| Component                    | Description                                                                                             | Contract                                                                            |
| ---------------------------- | ------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| **Domain Model**             | Defines the core entities, value objects, and ubiquitous language of the application.                   | [Domain Model & Ubiquous Language](./core/domain_model.md)                   |
| **ExecutionReport**          | A strongly-typed, immutable data structure representing the outcome of a plan execution.                | [ExecutionReport](./core/domain/execution_report.md)                           |
| **ShellOutput**              | A strictly-typed DTO representing the result of a shell command execution.                              | [ShellOutput](./core/domain/shell_output.md)                                   |
| **WebSearchResults**         | A strictly-typed DTO representing the aggregated results from a web search.                             | [WebSearchResults](./core/domain/web_search_results.md)                        |
| **ProjectContext**           | A strictly-typed DTO representing the aggregated project context for display.                           | [ProjectContext](./core/domain/project_context.md)                             |
| **IGetContextUseCase**       | Defines the inbound port for orchestrating the collection of project context.                           | [IGetContextUseCase](./core/ports/inbound/get_context_use_case.md)             |
| **IRunPlanUseCase**          | Defines the primary inbound port for executing a plan from a raw YAML string.                           | [IRunPlanUseCase](./core/ports/inbound/run_plan_use_case.md)                   |
| **IPlanParser**              | Defines the inbound port for parsing a plan from a raw string into a `Plan` object.                     | [IPlanParser](./core/ports/inbound/plan_parser.md)                             |
| **IPlanValidator**           | Defines the inbound port for performing pre-flight validation of a `Plan` object.                       | [IPlanValidator](./core/ports/inbound/plan_validator.md)                       |
| **IEnvironmentInspector**    | Defines the outbound port for gathering information about the host operating environment.               | [IEnvironmentInspector](./core/ports/outbound/environment_inspector.md)        |
| **IFileSystemManager**       | Defines a technology-agnostic outbound port for all file system operations (create, read, edit).        | [IFileSystemManager](./core/ports/outbound/file_system_manager.md)             |
| **IMarkdownReportFormatter** | Defines the outbound port for formatting an `ExecutionReport` into a Markdown string.                   | [IMarkdownReportFormatter](./core/ports/outbound/markdown_report_formatter.md) |
| **IRepoTreeGenerator**       | Defines the outbound port for generating a file tree, respecting `.gitignore` and `.teddyignore` files. | [IRepoTreeGenerator](./core/ports/outbound/repo_tree_generator.md)             |
| **IShellExecutor**           | Defines the outbound port for executing shell commands and returning a `ShellOutput` DTO.               | [IShellExecutor](./core/ports/outbound/shell_executor.md)                      |
| **IUserInteractor**          | Defines the outbound port for prompting the user for confirmation and free-text input.                  | [IUserInteractor](./core/ports/outbound/user_interactor.md)                    |
| **IWebScraper**              | Defines the outbound port for fetching and converting remote web page content to Markdown.              | [IWebScraper](./core/ports/outbound/web_scraper.md)                            |
| **IWebSearcher**             | Defines the outbound port for performing web searches and returning structured results.                 | [IWebSearcher](./core/ports/outbound/web_searcher.md)                          |
| **ActionDispatcher**         | A service that resolves and executes a single action, delegating to the `ActionFactory`.                | [ActionDispatcher](./core/services/action_dispatcher.md)                       |
| **ActionFactory**            | A factory service that creates validated `Action` domain objects from raw plan data.                    | [ActionFactory](./core/services/action_factory.md)                             |
| **ContextService**           | The service that implements `IGetContextUseCase` by orchestrating outbound ports to gather and format project context. | [ContextService](./core/services/context_service.md)                           |
| **ExecutionOrchestrator**    | The primary service that implements `IRunPlanUseCase`, managing the step-by-step execution of a parsed `Plan` object. | [ExecutionOrchestrator](./core/services/execution_orchestrator.md)             |
| **MarkdownPlanParser**       | A service that parses a Markdown plan string into a `Plan` domain object using a strict, single-pass AST traversal. | [MarkdownPlanParser](./core/services/markdown_plan_parser.md)                  |
| **MarkdownReportFormatter**  | Implements `IMarkdownReportFormatter` using the Jinja2 template engine to generate CLI reports.         | [MarkdownReportFormatter](./core/services/markdown_report_formatter.md)        |
| **PlanValidator**            | Implements `IPlanValidator` using a strategy pattern to run pre-flight checks on a plan's actions.      | [PlanValidator](./core/services/plan_validator.md)                             |

#### Primary Adapters

| Component                      | Description                                                                                | Contract                                                                                        |
| ------------------------------ | ------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------- |
| **CLI Adapter**                | The primary inbound adapter that drives the application via the `Typer` CLI framework.     | [CLI Adapter](./adapters/inbound/cli.md)                                          |
| **ConsoleInteractor**          | Implements `IUserInteractor` for the console, providing diff previews for file operations. | [ConsoleInteractorAdapter](./adapters/outbound/console_interactor.md)             |
| **LocalFileSystemAdapter**     | Implements `IFileSystemManager` for the local disk using Python's `pathlib`.               | [LocalFileSystemAdapter](./adapters/outbound/local_file_system_adapter.md)        |
| **LocalRepoTreeGenerator**     | Implements `IRepoTreeGenerator` using the `pathspec` library to handle ignore files.       | [LocalRepoTreeGenerator](./adapters/outbound/local_repo_tree_generator.md)        |
| **ShellAdapter**               | Implements `IShellExecutor` using Python's `subprocess` module.                            | [ShellAdapter](./adapters/outbound/shell_adapter.md)                              |
| **SystemEnvironmentInspector** | Implements `IEnvironmentInspector` using Python's `os`, `platform`, and `sys` modules.     | [SystemEnvironmentInspector](./adapters/outbound/system_environment_inspector.md) |
| **WebScraperAdapter**          | Implements `IWebScraper` using `trafilatura` for content extraction and a direct-fetch for GitHub URLs. | [WebScraperAdapter](./adapters/outbound/web_scraper_adapter.md)                   |
| **WebSearcherAdapter**         | Implements `IWebSearcher` using the `ddgs` library for keyless DuckDuckGo searches.        | [WebSearcherAdapter](./adapters/outbound/web_searcher_adapter.md)                 |

---

## 3. Key Architectural Decisions

This section captures significant, long-standing architectural decisions and patterns that define the system's design.

-   **Hexagonal Architecture:** The core business logic is isolated from external frameworks and I/O, enabling independent testing and technology swapping.
-   **Dependency Injection (DI):** The composition root in `main.py` uses the `punq` library to manage and inject dependencies, decoupling services from concrete implementations.
-   **"White-Box" Acceptance Testing:** All acceptance tests use `typer.testing.CliRunner` to run the CLI application in-process. This is the required pattern as it ensures mocks are respected and is faster and more reliable than testing via `subprocess`.
-   **Static vs. Runtime Type Checking:** The test suite, using `pytest`, does not enforce type hint contracts at runtime (e.g., it will not fail if a function returns a `dict` when an `object` is expected). Type safety and contract adherence between components (such as an adapter correctly implementing a port's interface) are enforced statically by `mypy` as part of the mandatory `pre-commit` checks.
-   **Structured Output Parsing in Tests:** Acceptance tests that verify structured output (e.g., YAML) MUST parse the output into a data structure before making assertions. This makes tests resilient to formatting changes.
-   **Separation of I/O Concerns:** The `[PLAN_FILE]` positional argument is the canonical way to provide a plan from a file, while omitting it defaults to reading from the clipboard. This reserves `stdin` exclusively for interactive prompts (like `y/n` or `chat_with_user`).
-   **Test Plan Injection:** The `execute` subcommand includes a `--plan-content` option. This is the canonical way to provide a plan as a string directly from within a test, making acceptance tests more robust and self-contained by avoiding file I/O or clipboard dependencies.
-   **Context Configuration:** The `context` command's behavior is explicitly driven by the contents of `.teddy/*.context` files, providing a clear, user-configurable contract.
-   **Interactive Diff Previews:** During interactive execution, `create` and `edit` actions provide a visual diff. This feature is configured via a prioritized strategy: the `TEDDY_DIFF_TOOL` environment variable, a fallback to the `code` (VS Code) CLI if present, and a final fallback to an in-terminal view. This provides a better user experience while remaining environment-agnostic.
-   **Dependency Versioning:** Dependency updates, even minor ones, can introduce breaking API changes (e.g., `typer.testing.CliRunner` API change in a `typer` update). While flexible version specifiers (`^X.Y.Z`) are convenient, production dependencies should be reviewed and potentially pinned to specific versions to improve stability and prevent unexpected CI failures.
-   **Cross-Platform Shell Execution (The "Smart Router"):** To handle the fundamental differences between POSIX and Windows command execution, the `ShellAdapter` employs a platform-specific strategy.
    -   **POSIX:** Uses `shell=True` and passes the raw command string. This approach is chosen to support shell features like globbing and pipes directly. The security risks typically associated with `shell=True` are mitigated by TeDDy's core workflow, which requires the user to approve every command before execution.
    -   **Windows:** Uses a "Smart Router" that inspects the command to decide whether to use a shell.
        -   It first checks if the command (e.g., `python.exe`) is a known executable file using `shutil.which()`. If it is, the command is executed directly with `shell=False`.
        -   If the command is not found as an executable, it is assumed to be a shell built-in (e.g., `dir`), and it is executed with `shell=True`.
    -   **Rationale:** This hybrid strategy provides maximum compatibility. On Windows, it avoids the complex and error-prone quoting issues of `list2cmdline` by passing raw command strings. On POSIX, it provides the power and convenience of the shell in a supervised environment.
-   **Defensive Type Handling for `mistletoe`:** The `mistletoe` Markdown parsing library exhibits a discrepancy between its runtime behavior and its static type hints. Specifically, attributes like `Token.children` are typed as a nullable `Iterable` but are consistently `list` instances at runtime.
    -   **Required Pattern:** To satisfy `mypy` and prevent runtime errors, any access to these attributes MUST be defensively converted to a concrete, non-nullable list first. Example: `children_list = list(token.children) if token.children else []`. This pattern ensures type safety and makes the code resilient to the library's loose type definitions.
-   **Single-Pass AST Parsing:** To ensure robustness against Markdown quirks (like `ThematicBreak` separators) and to simplify the parsing logic, the `MarkdownPlanParser` MUST use a "Single-Pass" strategy. It iterates through the AST nodes as a stream, dispatching to specific action parsers when an Action Heading is encountered and safely ignoring all interstitial content. This replaces the fragile "whitelist validation" approach.
-   **Cross-Platform File I/O:** All operations that read from or write to text files MUST explicitly specify `encoding="utf-8"`. This applies to both application code (`src/`) and test code (`tests/`).
    -   **Rationale:** The default file encoding is platform-dependent (e.g., UTF-8 on macOS/Linux, but often `cp1252` on Windows). Failing to specify the encoding can lead to `UnicodeEncodeError` or `UnicodeDecodeError` when handling files with non-ASCII characters on different operating systems. This convention ensures predictable, platform-agnostic behavior.
-   **Cross-Platform Path Normalization:** To distinguish project-relative paths (e.g., `[/docs/spec.md]`) from true absolute paths, the `MarkdownPlanParser` uses an OS-aware heuristic.
    -   **Rule:** A path is considered a "true" absolute path only if it starts with a common system directory on POSIX (e.g., `/tmp`, `/etc`) or a drive letter on Windows. Other paths starting with `/` are treated as project-relative.
    -   **Rationale:** This allows the parser to normalize project-relative paths (by stripping the leading slash) while preserving true absolute paths to be rejected by the `PlanValidator`, ensuring consistent security and behavior across platforms.
-   **Strict Parser Validation:** The `MarkdownPlanParser` must enforce a strict structure within a plan's `## Action Plan` section.
    -   **Rule:** Any content found between valid action blocks (e.g., a `ThematicBreak` (`---`) or stray paragraphs) must be treated as a validation error. The parser should not attempt to ignore or "auto-correct" malformed plan structures.
    -   **Rationale:** This decision was the result of a pivot from an initial "robustness-first" approach. A strict, fail-fast parser is simpler, more predictable, and forces the upstream AI agent to produce well-formed plans, which is a core principle of the TeDDy workflow.

---

## 4. Debug Mode

To aid in fault isolation, the `teddy` executor includes a debug mode that can be activated via an environment variable.

-   **Activation:** Set the `TEDDY_DEBUG` environment variable to any non-empty value (e.g., `export TEDDY_DEBUG=true`).
-   **Behavior:** When active, this mode enables detailed logging for specific, hard-to-diagnose components.
    -   **`MarkdownPlanParser`:** Prints a detailed Abstract Syntax Tree (AST) of the parsed plan to standard output. This is crucial for debugging parsing logic and issues related to Markdown structure.
