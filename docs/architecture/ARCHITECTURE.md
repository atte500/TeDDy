# System Architecture: TeDDy

This document outlines the technical standards, conventions, and setup process for the `TeDDy` project.

## 1. Conventions & Standards

- **Version Control:** Default to Trunk-Based Development on main. Commits MUST follow Conventional Commits.
- **Run Environment:** All execution commands MUST be prefixed with the project's designated runner ('poetry run').
- **Failure Transparency:** Silent error suppression is strictly forbidden. Generic catch-all blocks MUST NOT be used to swallow errors. Every try/catch block MUST either catch a specific error type or ensure generic catches log full context and re-raise. Empty catch blocks are only allowed with an explicit "safe to ignore" comment.
- **Testing Strategy:** Define structural rules (Unit > Integration > Acceptance) and mandate designated temporary directories for detritus (`tests/.tmp/`). The Test Harness is a first-class boundary requiring its own unit tests. Mandate: Real domain objects for logic; In-Memory Fakes for state-managing Outbound Ports; Mocks ONLY for un-verifiable external side-effects. To prevent Mock Poisoning, any allowed Mocks MUST strictly bind to their target contracts (e.g., via the project's designated mock registration helper that enforces auto-speccing) to prevent Signature Drift. Direct instantiation of bare, dynamic mock objects is strictly forbidden. Global/runtime module patching is strictly forbidden to prevent State Leakage; swap dependencies explicitly via Constructor Injection. Ensure the suite is designed to be fast and parallelized.
- **Dependency Injection:** Mandate strict Constructor Injection for all core domain services. All dependencies MUST be passed explicitly via constructors. Defaulting to null or dynamic resolution via a global or passed container is strictly forbidden. Core domain logic MUST NOT import or depend on external Dependency Injection frameworks or containers.
- **Centralized Configuration:** Hardcoded "magic numbers" or scattered fallback values for application logic are strictly forbidden. All configurable parameters MUST be centralized in the project's designated configuration layer (e.g., `IConfigService`).
- **CI Pipeline:** Define two parallel jobs: 1) Blocking OS matrix test suite with strict test coverage targets. 2) Non-blocking (continue-on-error: true) quality checks running fast formatters, linters, security/secret scanners, type checkers, and repository-wide structural checks (excluding sandboxes and third-party dependencies).
- **Pre-commit Hooks:** Local pre-commit MUST be scoped strictly to staged files to ensure fast feedback loops. Hooks MUST include fast formatters, linters, security/secrets scanners, static type-checkers, automated DI boundary verifiers (ensuring core domain logic has zero external DI container imports), and rules to ban bare mock objects in favor of the designated mock registration helper.
- **Post-commit Execution:** The full test suite runs in a post-commit hook as an unskippable safety net. If tests fail, the commit is automatically reverted via `git reset --soft HEAD~1`, keeping changes staged for investigation. This ensures `--no-verify` cannot bypass the test gate.

### Experimental Code
The `spikes/` directory is for rapid, isolated experimentation (including `debug/`, `prototypes/`, and `showcases/`) and is explicitly excluded from all quality gates (linting, types, complexity).

---

## 2. Component & Boundary Map

This section serves as both the strategic **Boundary Map** and the detailed **Component Map** for the system.

**Boundary Analysis:** The `teddy_executor` follows a Hexagonal Architecture. The boundary separates the core business logic (domain models, services, and ports) from the platform-specific integration layer (the CLI) and infrastructure (the local filesystem, shell, and web). **Primary Adapters** act as the explicit translation layer across this boundary, ensuring the core remains isolated and independently testable.

### `teddy_executor` Package

#### Hexagonal Core

| Component                     | Description                                                                                                                                         | Contract                                                                         |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| **Domain Model**              | Defines the core entities, value objects, and ubiquitous language of the application.                                                               | [Domain Model & Ubiquous Language](./core/domain_model.md)                       |
| **ExecutionReport**           | A strongly-typed, immutable data structure representing the outcome of a plan execution.                                                            | [ExecutionReport](./core/domain/execution_report.md)                             |
| **ShellOutput**               | A strictly-typed DTO representing the result of a shell command execution.                                                                          | [ShellOutput](./core/domain/shell_output.md)                                     |
| **WebSearchResults**          | A strictly-typed DTO representing the aggregated results from a web search.                                                                         | [WebSearchResults](./core/domain/web_search_results.md)                          |
| **ProjectContext**            | A strictly-typed DTO representing the aggregated project context for display.                                                                       | [ProjectContext](./core/domain/project_context.md)                               |
| **ActionPorts**               | A DTO grouping the outbound ports required by the ActionFactory to maintain low constructor complexity.                                             | [ActionPorts](./core/domain/action_ports.md)                                     |
| **IGetContextUseCase**        | Defines the inbound port for orchestrating the collection of project context.                                                                       | [IGetContextUseCase](./core/ports/inbound/get_context_use_case.md)               |
| **IInitUseCase**              | Defines the inbound port for project auto-initialization.                                                                                           | [IInitUseCase](./core/ports/inbound/init.md)                                     |
| **IRunPlanUseCase**           | Defines the primary inbound port for executing a plan from a raw YAML string.                                                                       | [IRunPlanUseCase](./core/ports/inbound/run_plan_use_case.md)                     |
| **IPlanningUseCase**          | Defines the inbound port for generating a plan from a user message.                                                                                 | [IPlanningUseCase](./core/ports/inbound/planning_use_case.md)                    |
| **IPlanReviewer**             | Defines the inbound port for the interactive review and modification of a plan.                                                                     | [IPlanReviewer](./core/ports/inbound/plan_reviewer.md)                           |
| **IPlanParser**               | Defines the inbound port for parsing a plan from a raw string into a `Plan` object.                                                                 | [IPlanParser](./core/ports/inbound/plan_parser.md)                               |
| **IPlanValidator**            | Defines the inbound port for performing pre-flight validation of a `Plan` object.                                                                   | [IPlanValidator](./core/ports/inbound/plan_validator.md)                         |
| **IPlanReviewer**             | Defines the inbound port for the interactive review and modification of a plan.                                                                     | [IPlanReviewer](./core/ports/inbound/plan_reviewer.md)                           |
| **IConfigService**            | Defines the outbound port for retrieving application configuration and secrets.                                                                     | [IConfigService](./core/ports/outbound/config_service.md)                        |
| **IExecutionReportAssembler** | Defines the outbound port for assembling an `ExecutionReport` from execution outcome data.                                                          | [IExecutionReportAssembler](./core/ports/outbound/execution_report_assembler.md) |
| **IEnvironmentInspector**     | Defines the outbound port for gathering information about the host operating environment.                                                           | [IEnvironmentInspector](./core/ports/outbound/environment_inspector.md)          |
| **IFileSystemManager**        | Defines a technology-agnostic outbound port for all file system operations (create, read, edit).                                                    | [IFileSystemManager](./core/ports/outbound/file_system_manager.md)               |
| **ILlmClient**                | Defines the outbound port for communicating with a Large Language Model.                                                                            | [ILlmClient](./core/ports/outbound/llm_client.md)                                |
| **IMarkdownReportFormatter**  | Defines the outbound port for formatting an `ExecutionReport` into a Markdown string.                                                               | [IMarkdownReportFormatter](./core/ports/outbound/markdown_report_formatter.md)   |
| **IRepoTreeGenerator**        | Defines the outbound port for generating a file tree, respecting `.gitignore` and `.teddyignore` files.                                             | [IRepoTreeGenerator](./core/ports/outbound/repo_tree_generator.md)               |
| **IShellExecutor**            | Defines the outbound port for executing shell commands and returning a `ShellOutput` DTO.                                                           | [IShellExecutor](./core/ports/outbound/shell_executor.md)                        |
| **IUserInteractor**           | Defines the outbound port for prompting the user for confirmation and free-text input.                                                              | [IUserInteractor](./core/ports/outbound/user_interactor.md)                      |
| **IWebScraper**               | Defines the outbound port for fetching and converting remote web page content to Markdown.                                                          | [IWebScraper](./core/ports/outbound/web_scraper.md)                              |
| **IWebSearcher**              | Defines the outbound port for performing web searches and returning structured results.                                                             | [IWebSearcher](./core/ports/outbound/web_searcher.md)                            |
| **ActionDispatcher**          | A service that resolves and executes a single action, delegating to the `ActionFactory`.                                                            | [ActionDispatcher](./core/services/action_dispatcher.md)                         |
| **ActionFactory**             | A factory service that creates validated `Action` domain objects from raw plan data.                                                                | [ActionFactory](./core/services/action_factory.md)                               |
| **EditSimulator**             | A pure service for applying a sequence of FIND/REPLACE edits to a string in memory.                                                                 | [EditSimulator](./core/services/edit_simulator.md)                               |
| **ContextService**            | The service that implements `IGetContextUseCase` by orchestrating outbound ports to gather and format project context.                              | [ContextService](./core/services/context_service.md)                             |
| **ExecutionOrchestrator**     | The primary service that implements `IRunPlanUseCase`, managing the step-by-step execution of a parsed `Plan` object.                               | [ExecutionOrchestrator](./core/services/execution_orchestrator.md)               |
| **InitService**               | The service that implements `IInitUseCase`, ensuring projects are initialized before command execution. Supports a configurable template directory. | [InitService](./core/services/init_service.md)                                   |
| **PlanningService**           | Orchestrates context gathering and LLM interaction to generate plans.                                                                               | [PlanningService](./core/services/planning_service.md)                           |
| **ISessionManager**           | Defines the outbound port for managing turn directories and metadata persistence.                                                                   | [ISessionManager](./core/ports/outbound/session_manager.md)                      |
| **SessionService**            | Implements `ISessionManager` to manage the filesystem structure and metadata for TeDDy sessions.                                                    | [SessionService](./core/services/session_service.md)                             |
| **PromptManager**             | Resolves agent prompts and turn metadata for the session audit trail.                                                                               | [PromptManager](./core/services/prompt_manager.md)                               |
| **SessionService**            | Manages the filesystem structure and machine-readable metadata for TeDDy sessions.                                                                  | [SessionService](./core/services/session_service.md)                             |
| **SessionOrchestrator**       | A wrapper service implementing the "Turn Transition Algorithm" and "Auto-Naming" logic.                                                             | [SessionOrchestrator](./core/services/session_orchestrator.md)                   |
| **SessionPlanner**            | Handles interactive turn planning and dynamic session renaming.                                                                                     | [SessionPlanner](./core/services/session_planner.md)                             |
| **MarkdownPlanParser**        | A service that parses a Markdown plan string into a `Plan` domain object using a strict, single-pass AST traversal.                                 | [MarkdownPlanParser](./core/services/markdown_plan_parser.md)                    |
| **Action Parser Strategies**  | A set of strategy functions for parsing specific action types within a plan.                                                                        | [ActionParserStrategies](./core/services/action_parser_strategies.md)            |
| **Parser Metadata**           | Specialized logic for extracting parameters from metadata lists and messages during plan parsing.                                                   | [ParserMetadata](./core/services/parser_metadata.md)                             |
| **Parser Infrastructure**     | Low-level utilities for AST traversal, stream management, and path normalization used during plan parsing.                                          | [ParserInfrastructure](./core/services/parser_infrastructure.md)                 |
| **MarkdownReportFormatter**   | Implements `IMarkdownReportFormatter` using the Jinja2 template engine to generate CLI reports.                                                     | [MarkdownReportFormatter](./core/services/markdown_report_formatter.md)          |
| **PlanValidator**             | Implements `IPlanValidator` using a strategy pattern to run pre-flight checks on a plan's actions.                                                  | [PlanValidator](./core/services/plan_validator.md)                               |

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
| **WebSearcherAdapter**         | Implements `IWebSearcher` using the `ddgs` library for DuckDuckGo searches with automated follow-up scraping.        | [WebSearcherAdapter](./adapters/outbound/web_searcher_adapter.md)                 |
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
- **Cross-Platform Path Assertions:** All tests performing path-based assertions MUST use the `POSIXPathMock.find_call_by_path(method, path)` helper. Manual inspection of `call_args_list` with `str()` comparisons is strictly forbidden as it breaks on Windows due to slash mismatches. (Ensures CI stability across OS matrix.)
- **Execute Action:** Allow shell chaining and inline directives. (Simplifies protocol and maintains statelessness.)
- **Windows Failure:** Use `cmd /c` to isolate terminating commands. (Ensures parent process can report failures.)
- **Reporting:** Use Jinja2 Macros for modularity. (Ensures consistency and facilitates section extraction.)
- **Encoding:** Explicitly specify `utf-8` for all file operations. (Ensures predictable platform-agnostic behavior.)
- **Serialization:** Enforce strict primitive validation before serialization. (Prevents infinite recursion or hangs from dynamic objects.)
- **DI Boundaries:** The `src/.../core/` directory MUST NOT import or depend on DI frameworks (e.g., `punq`). (Ensures Hexagonal isolation and prevents Service Locator anti-patterns.)
- **Constructor Injection:** All core services MUST use explicit constructor injection. (Mandates transparency and simplifies testing.)
- **Initialization:** Import heavy libraries (`litellm`, `trafilatura`) lazily. (Ensures CLI initializes under 500ms.)
- **Binary Stability:** Abstract heavy binary libs into private getters and mock the getter. (Prevents worker crashes in distributed tests.)
- **Performance:** Optimize core logic and plan validation for performance on large inputs to ensure low-latency feedback loops.
- **Pre-commit Workflow:** Scope local checks strictly to staged files. (Ensures fast feedback loops while delegating global checks to CI.)
- **Transient Resilience:** Outbound adapters for unreliable remote services (LLM, Web) MUST implement stateful retry logic (default 3 attempts) for known transient failure modes (SSL, Timeout, 5xx).
- **Web Content Cache:** Session-level web content is cached in a JSON file at `<session_root>/.web_cache.json`. The cache is a flat dict mapping URL → content string. The cache file is read once per context assembly, updated atomically (write to temp file, rename) on each successful fetch. Missing or corrupt cache files are treated as empty cache. No TTL is applied; caching is intra-session only.


---

## 4. Debug Mode & Branch by Abstraction

- **Activation:** Use scoped environment toggles (e.g., `APP_DEBUG=auth,parser`).
- **Zero-Cost Guards:** All debug and prototype logic MUST use language-native dead-code elimination (e.g., `if __debug__:`) to ensure zero performance impact in production.
- **Branch by Abstraction:** All behavioral alternatives MUST be injected at the Composition Root via Constructor Injection. Mid-logic environment checks are strictly forbidden.
- **State Dumps:** Diagnostics should write transient state to `.tmp/debug/`.
