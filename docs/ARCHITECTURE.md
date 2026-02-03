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

### Command Execution with Poetry
- **Principle:** Commands are executed from the **project root**, but `poetry`'s `-C` flag changes the working directory *before* the command runs. For example, `poetry -C packages/executor run ...` executes the command as if you were already inside the `packages/executor/` directory.
- **Rule:** All file paths provided to such commands **MUST be relative to the package directory**, not the project root.
- **Correct Pattern:**
  ```bash
  # Correctly provides a path relative to packages/executor/
  poetry -C packages/executor run pytest tests/acceptance/test_chat_with_user_action.py
  ```
- **Incorrect Pattern:**
  ```bash
  # Incorrectly duplicates the path because the CWD is already packages/executor/
  poetry -C packages/executor run pytest packages/executor/tests/acceptance/test_quality_of_life_improvements.py
  ```

### Testing Strategy
- **Framework:** `pytest`.
- **Location of Tests:** Within each package, tests are organized as follows:
    - `tests/acceptance/`: End-to-end tests.
    - `tests/integration/`: Tests for components that interact with external systems.
    - `tests/unit/`: Tests for individual functions or classes in isolation.
- **Execution:** Tests are run from the **project root** using the `poetry -C` flag. See the **"Command Execution with Poetry"** section for the required path conventions.
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

### Third-Party Dependency Vetting
- **Strategy:** Mandate a "Verify, Then Document" Spike for new dependencies.
- **Rationale:** Based on the RCA for a failure involving the `gitwalk` library ([see RCA](./rca/unreliable-third-party-library-gitwalk.md)), new third-party dependencies must be de-risked before integration.
- **Process:** Before a new dependency is used, a minimal technical spike must prove its core functionality. The successful spike script should be referenced in the final adapter design document.

---

## 3. Component & Boundary Map

This section serves as both the strategic **Boundary Map** and the detailed **Component Map** for the system.

**Boundary Analysis:** The `executor` package follows a Hexagonal Architecture. The boundary separates the core business logic (domain models, services, and ports) from the platform-specific integration layer (the CLI) and infrastructure (the local filesystem, shell, and web). **Primary Adapters** act as the explicit translation layer across this boundary, ensuring the core remains isolated and independently testable.

### `executor` Package

#### Hexagonal Core

| Component                 | Description                                                                                             | Contract                                                                             |
| ------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| **Domain Model**          | Defines the core entities, value objects, and ubiquitous language of the application.                   | [Domain Model & Ubiquitous Language](./contexts/executor/domain_model.md)            |
| **ExecutionReport**       | A strongly-typed, immutable data structure representing the outcome of a plan execution.                | [ExecutionReport](./contexts/executor/domain/execution_report.md)                    |
| **IGetContextUseCase**    | Defines the inbound port for orchestrating the collection of project context.                           | [IGetContextUseCase](./contexts/executor/ports/inbound/get_context_use_case.md)      |
| **IRunPlanUseCase**       | Defines the primary inbound port for executing a plan from a raw YAML string.                           | [IRunPlanUseCase](./contexts/executor/ports/inbound/run_plan_use_case.md)            |
| **IEnvironmentInspector** | Defines the outbound port for gathering information about the host operating environment.               | [IEnvironmentInspector](./contexts/executor/ports/outbound/environment_inspector.md) |
| **IFileSystemManager**    | Defines a technology-agnostic outbound port for all file system operations (create, read, edit).        | [IFileSystemManager](./contexts/executor/ports/outbound/file_system_manager.md)      |
| **IRepoTreeGenerator**    | Defines the outbound port for generating a file tree, respecting `.gitignore` and `.teddyignore` files. | [IRepoTreeGenerator](./contexts/executor/ports/outbound/repo_tree_generator.md)      |
| **IShellExecutor**        | Defines the outbound port for executing shell commands in a specific context (CWD, env).                | [IShellExecutor](./contexts/executor/ports/outbound/shell_executor.md)               |
| **IUserInteractor**       | Defines the outbound port for prompting the user for confirmation and free-text input.                  | [IUserInteractor](./contexts/executor/ports/outbound/user_interactor.md)             |
| **IWebScraper**           | Defines the outbound port for fetching and converting remote web page content to Markdown.              | [IWebScraper](./contexts/executor/ports/outbound/web_scraper.md)                     |
| **IWebSearcher**          | Defines the outbound port for performing web searches and returning structured results.                 | [IWebSearcher](./contexts/executor/ports/outbound/web_searcher.md)                   |
| **ActionDispatcher**      | A service that resolves and executes a single action, delegating to the `ActionFactory`.                | [ActionDispatcher](./contexts/executor/services/action_dispatcher.md)                |
| **ActionFactory**         | A factory service that creates validated `Action` domain objects from raw plan data.                    | [ActionFactory](./contexts/executor/services/action_factory.md)                      |
| **ContextService**        | The service that implements `IGetContextUseCase` by orchestrating outbound ports.                       | [ContextService](./contexts/executor/services/context_service.md)                    |
| **ExecutionOrchestrator** | The primary service that implements `IRunPlanUseCase`, managing the step-by-step execution of a plan.   | [ExecutionOrchestrator](./contexts/executor/services/execution_orchestrator.md)      |
| **PlanParser**            | A service that parses a YAML plan string into a structured `Plan` domain object, handling validation.   | [PlanParser](./contexts/executor/services/plan_parser.md)                            |

#### Primary Adapters

| Component                      | Description                                                                                | Contract                                                                                   |
| ------------------------------ | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ |
| **CLI Adapter**                | The primary inbound adapter that drives the application via the `Typer` CLI framework.     | [CLI Adapter](./adapters/executor/inbound/cli.md)                                          |
| **ConsoleInteractor**          | Implements `IUserInteractor` for the console, providing diff previews for file operations. | [ConsoleInteractorAdapter](./adapters/executor/outbound/console_interactor.md)             |
| **LocalFileSystemAdapter**     | Implements `IFileSystemManager` for the local disk using Python's `pathlib`.               | [LocalFileSystemAdapter](./adapters/executor/outbound/local_file_system_adapter.md)        |
| **LocalRepoTreeGenerator**     | Implements `IRepoTreeGenerator` using the `pathspec` library to handle ignore files.       | [LocalRepoTreeGenerator](./adapters/executor/outbound/local_repo_tree_generator.md)        |
| **ShellAdapter**               | Implements `IShellExecutor` using Python's `subprocess` module.                            | [ShellAdapter](./adapters/executor/outbound/shell_adapter.md)                              |
| **SystemEnvironmentInspector** | Implements `IEnvironmentInspector` using Python's `os`, `platform`, and `sys` modules.     | [SystemEnvironmentInspector](./adapters/executor/outbound/system_environment_inspector.md) |
| **WebScraperAdapter**          | Implements `IWebScraper` using the `requests` and `markdownify` libraries.                 | [WebScraperAdapter](./adapters/executor/outbound/web_scraper_adapter.md)                   |
| **WebSearcherAdapter**         | Implements `IWebSearcher` using the `ddgs` library for keyless DuckDuckGo searches.        | [WebSearcherAdapter](./adapters/executor/outbound/web_searcher_adapter.md)                 |

---

## 4. Key Architectural Decisions

This section captures significant, long-standing architectural decisions and patterns that define the system's design.

-   **Hexagonal Architecture:** The core business logic is isolated from external frameworks and I/O, enabling independent testing and technology swapping.
-   **Dependency Injection (DI):** The composition root in `main.py` uses the `punq` library to manage and inject dependencies, decoupling services from concrete implementations.
-   **"White-Box" Acceptance Testing:** All acceptance tests use `typer.testing.CliRunner` to run the CLI application in-process. This is the required pattern as it ensures mocks are respected and is faster and more reliable than testing via `subprocess`.
-   **Structured Output Parsing in Tests:** Acceptance tests that verify structured output (e.g., YAML) MUST parse the output into a data structure before making assertions. This makes tests resilient to formatting changes.
-   **Separation of I/O Concerns:** The `[PLAN_FILE]` positional argument is the canonical way to provide a plan from a file, while omitting it defaults to reading from the clipboard. This reserves `stdin` exclusively for interactive prompts (like `y/n` or `chat_with_user`).
-   **Test Plan Injection:** The `execute` subcommand includes a `--plan-content` option. This is the canonical way to provide a plan as a string directly from within a test, making acceptance tests more robust and self-contained by avoiding file I/O or clipboard dependencies.
-   **Context Configuration:** The `context` command's behavior is explicitly driven by the contents of `.teddy/*.context` files, providing a clear, user-configurable contract.
-   **Interactive Diff Previews:** During interactive execution, `create` and `edit` actions provide a visual diff. This feature is configured via a prioritized strategy: the `TEDDY_DIFF_TOOL` environment variable, a fallback to the `code` (VS Code) CLI if present, and a final fallback to an in-terminal view. This provides a better user experience while remaining environment-agnostic.
-   **Dependency Versioning:** Dependency updates, even minor ones, can introduce breaking API changes (e.g., `typer.testing.CliRunner` API change in a `typer` update). While flexible version specifiers (`^X.Y.Z`) are convenient, production dependencies should be reviewed and potentially pinned to specific versions to improve stability and prevent unexpected CI failures.

---

## 6. YAML Plan Specification

This section defines the formal contract for the `actions` list in a `plan.yaml` file used by the `teddy execute` command. Each item in the list is a dictionary representing a single action.

**Structure:**
```yaml
actions:
  - action: <action_type>
    description: <A human-readable description of the action's purpose>
    <parameter_1>: <value_1>
    ...
```

**Required Keys:**
-   `action` (or `type`): Specifies the type of operation to perform.
-   `description`: A string that describes the action's purpose. This is used for logging and interactive prompts. For `execute` actions, this field should summarize the expected outcome of the command.

All other keys are considered parameters specific to that action (e.g., `path`, `content`, `command`).

---

**Convention: Path Parameter Quoting**

To ensure cross-platform compatibility, any action parameter that accepts a file path (e.g., `path` in `create_file`, `read`, `edit`) **MUST** be enclosed in single quotes when its value is dynamically inserted into a YAML string (e.g., in a test fixture).

-   **Correct (Single-Quoted):** `f"path: '{my_path_var}'"`
-   **Incorrect (Double-Quoted):** `f'path: "{my_path_var}"'`

**Rationale:** The string representation of a path on Windows includes backslashes (`\`). In a double-quoted YAML string, a backslash is an escape character, which leads to a `YAMLError`. Single-quoted strings treat backslashes as literal characters, making them safe for file paths on all operating systems.

---

### `create_file`

Creates a new file with the specified content. If the file already exists, it will be overwritten.

**Parameters:**
-   `path` (string, required): The relative path to the file to create.
-   `content` (string, required): The content to write into the file.

**Example:**
```yaml
- action: create_file
  description: "Create a new Python module with a hello_world function."
  path: "src/new_module.py"
  content: |
    # src/new_module.py
    def hello_world():
        print("Hello, world!")
```

---

### `read`

Reads the full content of a specified file. The content is returned in the `details` field of the action log in the final execution report.

**Parameters:**
-   `path` (string, required): The relative path to the file to read.

**Example:**
```yaml
- action: read
  description: "Read the project's README file."
  path: "README.md"
```

---

### `edit`

Performs a find-and-replace operation on a file. It is designed for targeted, precise modifications.

**Parameters:**
-   `path` (string, required): The relative path to the file to edit.
-   `find` (string, required): The exact block of text to search for. Multi-line blocks are supported.
-   `replace` (string, required): The block of text that will replace the `find` block. Multi-line blocks and indentation are supported.

**Example (Multi-line with indentation):**
```yaml
- action: edit
  description: "Add a new method to my_class.py."
  path: "src/my_class.py"
  find: |
    def existing_method(self):
        """An existing method."""
        return self.value
  replace: |
    def existing_method(self):
        """An existing method."""
        return self.value

    def new_indented_method(self, multiplier):
        """A new method added via edit."""
        return self.value * multiplier
```

---

### `execute`

Executes a shell command in the current working directory.

**Parameters:**
-   `command` (string, required): The shell command to execute.
-   `cwd` (string, optional): A relative path to a different directory to run the command in.
-   `env` (dictionary, optional): A dictionary of environment variables to set for the command.

**Example:**
```yaml
- action: execute
  description: "Run the pytest test suite."
  command: "python -m pytest tests/"
```

---

### `research`

Performs a web search using a set of queries. The search results (title, URL, snippet) are returned in the `details` field of the action log.

**Parameters:**
-   `queries` (list of strings, required): A list of search queries to execute.

**Example:**
```yaml
- action: research
  description: "Find information on Python DI libraries and hexagonal architecture."
  queries:
    - "python dependency injection libraries"
    - "hexagonal architecture in python"
```

---

### `chat_with_user`

Prompts the user with a question during an interactive execution and waits for a free-text response. The user's response is returned in the `details.response` field of the action log.

**Parameters:**
-   `prompt` (string, required): The question to ask the user.

**Example Plan:**
```yaml
- action: chat_with_user
  description: "Get user's final decision on a library."
  prompt: "Based on the research, which DI library should I use?"
```

**Example Report Output:**
After the user responds (e.g., with "punq"), the corresponding `ActionLog` in the final report will look like this:

```yaml
- status: SUCCESS
  action_type: chat_with_user
  params:
    prompt: Based on the research, which DI library should I use?
  description: Get user's final decision on a library.
  details:
    response: punq
```
