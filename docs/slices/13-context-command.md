# Vertical Slice 13: Implement `context` Command

## 1. Business Goal

As a user preparing to interact with an AI, I need a simple command (`teddy context`) that gathers all relevant project information into a single, comprehensive output. This output should include a file tree, system information, and the contents of specified files, making it easy to provide the AI with a complete snapshot of the current working environment.

The command should also manage a local `.teddy` directory to store context file lists, separating the AI-managed context from a user-managed permanent context file.

## 2. Acceptance Criteria (Scenarios)

### Scenario: First-time run in a new project

*   **Given** I am in a project directory that does not contain a `.teddy` folder
*   **When** I run the `teddy context` command
*   **Then** a `.teddy` directory is created
*   **And** a `.teddy/.gitignore` file is created containing the line `*`
*   **And** a `.teddy/context.json` file is created (and is empty or has a default structure)
*   **And** a `.teddy/permanent_context.txt` file is created
*   **And** the `.teddy/permanent_context.txt` file contains default entries like `README.md`, `docs/ARCHITECTURE.md`, and `repotree.txt`.
*   **And** the output contains the repo tree, OS info, `.gitignore` content, and the content of `README.md` and `docs/ARCHITECTURE.md`.

### Scenario: Running the command with existing context files

*   **Given** a `.teddy` directory exists
*   **And** `.teddy/context.json` contains `["src/main.py"]`
*   **And** `.teddy/permanent_context.txt` contains `["pyproject.toml"]`
*   **When** I run the `teddy context` command
*   **Then** the output includes the contents of `src/main.py` and `pyproject.toml`.
*   **And** the output mentions if any file listed in the context files is not found.

### Scenario: Handling missing files gracefully

*   **Given** a `.teddy` directory exists
*   **And** `.teddy/permanent_context.txt` contains `["non_existent_file.txt"]`
*   **When** I run the `teddy context` command
*   **Then** the output still includes all other requested information
*   **And** the output contains a clear message indicating that `non_existent_file.txt` was not found.

## 3. Interaction Sequence

1.  User executes `teddy context` from the command line.
2.  The `CliInboundAdapter` receives the command and invokes the `GetContextUseCase` port on the `ContextService`.
3.  The `ContextService` orchestrates the gathering of information:
    a. It ensures the `.teddy` directory and its default files (`.gitignore`, `context.json`, `permanent_context.txt`) exist, creating them if necessary. This is handled via the `FileSystemManager` port.
    b. It reads the list of file paths from both `context.json` and `permanent_context.txt` via the `FileSystemManager` port.
    c. It requests the repository file tree (respecting `.gitignore`) from the `RepoTreeGenerator` port.
    d. It requests OS and terminal information from the `EnvironmentInspector` port.
    e. It reads the content of the main `.gitignore` file via the `FileSystemManager` port.
    f. For each file path gathered from the context lists, it reads its content via the `FileSystemManager` port, noting any files that are not found.
4.  The `ContextService` aggregates all this information into a structured `ContextResult` domain object.
5.  The `ContextService` returns the `ContextResult` object to the `CliInboundAdapter`.
6.  The `CliInboundAdapter` (via `CLIFormatter`) formats the `ContextResult` into a human-readable string and prints it to the console.

## 4. Scope of Work (Components)

*   **Hexagonal Core (New):**
    *   **Domain Model:** `ContextResult` (a dataclass to hold all the gathered info).
    *   **Inbound Port:** `IGetContextUseCase` (with a method like `get_context()`).
    *   **Application Service:** `ContextService` (implements `IGetContextUseCase`).
    *   **Outbound Port:** `IRepoTreeGenerator` (generates a file tree respecting `.gitignore`).
    *   **Outbound Port:** `IEnvironmentInspector` (gets OS/terminal info).
*   **Hexagonal Core (Updates):**
    *   **Outbound Port:** `IFileSystemManager` (needs to support checking existence, ensuring directory creation, and reading/writing context files).
*   **Adapters (New):**
    *   **Outbound Adapter:** `LocalRepoTreeGenerator` (implements `IRepoTreeGenerator`).
    *   **Outbound Adapter:** `SystemEnvironmentInspector` (implements `IEnvironmentInspector`).
*   **Adapters (Updates):**
    *   **Inbound Adapter:** `CLI` (add the new `context` command and wire it to the `ContextService`).
    *   **Outbound Adapter:** `LocalFileSystemAdapter` (implement new methods required by `IFileSystemManager`).

## 5. Scope of Work (Implementation)

This section provides a detailed, file-by-file checklist for the developer.

### Core Logic

-   [ ] **CREATE** `src/teddy/core/ports/inbound/get_context_use_case.py`
    -   Define the `IGetContextUseCase` protocol with a single method `get_context() -> ContextResult`.
-   [ ] **CREATE** `src/teddy/core/ports/outbound/repo_tree_generator.py`
    -   Define the `IRepoTreeGenerator` protocol with a single method `generate_tree() -> str`.
-   [ ] **CREATE** `src/teddy/core/ports/outbound/environment_inspector.py`
    -   Define the `IEnvironmentInspector` protocol with a single method `get_environment_info() -> dict[str, str]`.
-   [ ] **EDIT** `src/teddy/core/domain/models.py`
    -   Add the `FileContext` and `ContextResult` dataclasses as defined in the domain model documentation.
-   [ ] **EDIT** `src/teddy/core/ports/outbound/file_system_manager.py`
    -   Add `path_exists(path: str) -> bool`, `create_directory(path: str) -> None`, and `write_file(path: str, content: str) -> None` to the `IFileSystemManager` protocol.
    -   Update the `read_file` signature to return `str` and raise exceptions, removing the old `Result` object pattern.
-   [ ] **CREATE** `src/teddy/core/services/context_service.py`
    -   Create the `ContextService` class.
    -   Implement the `IGetContextUseCase` port.
    -   Inject `IFileSystemManager`, `IRepoTreeGenerator`, and `IEnvironmentInspector` as dependencies in the constructor.
    -   Implement the `get_context` method to orchestrate its dependencies as detailed in the Interaction Sequence.
-   [ ] **CREATE** `tests/unit/core/services/test_context_service.py`
    -   Write unit tests for `ContextService`.
    -   Use mocks for all outbound port dependencies to test the orchestration logic in isolation.
    -   Verify that the service correctly handles the creation of the `.teddy` directory on the first run.
    -   Verify that it correctly aggregates data from all its dependencies into the `ContextResult` object.

### Adapters

-   [ ] **CREATE** `src/teddy/adapters/outbound/local_repo_tree_generator.py`
    -   Create the `LocalRepoTreeGenerator` class implementing `IRepoTreeGenerator`.
    -   Implement the `generate_tree` method using `os.walk` and the `pathspec` library, following the verified solution in the RCA.
    -   Include a hardcoded set of directories to always ignore (e.g., `.git`, `.venv`, `__pycache__`).
-   [ ] **CREATE** `src/teddy/adapters/outbound/system_environment_inspector.py`
    -   Create the `SystemEnvironmentInspector` class implementing `IEnvironmentInspector`.
    -   Implement `get_environment_info` using the `platform`, `sys`, and `os` modules as verified in the spike.
-   [ ] **EDIT** `src/teddy/adapters/outbound/file_system_adapter.py`
    -   Implement the new methods: `path_exists`, `create_directory`, and `write_file` using `pathlib` as documented.
    -   Update the `read_file` implementation to raise standard exceptions (`FileNotFoundError`, etc.) instead of returning a `Result` object.
-   [ ] **EDIT** `src/teddy/adapters/inbound/cli_formatter.py`
    -   Create a new function `format_project_context(context: ContextResult) -> str`.
    -   This function should render the `ContextResult` object into a well-structured string with clear headings for each section.
-   [ ] **EDIT** `src/teddy/main.py` (or CLI definition file)
    -   Add a new Typer command function for `context`.
    -   In the composition root, wire up the `ContextService` with its concrete adapter dependencies (`LocalFileSystemAdapter`, `LocalRepoTreeGenerator`, `SystemEnvironmentInspector`).
    -   The command function should call the `ContextService`, pass the result to the new `format_project_context` formatter, and print the output.

### Testing

-   [ ] **CREATE** `tests/integration/adapters/outbound/test_local_repo_tree_generator.py`
    -   Implement the regression test recommended in the RCA (`docs/rca/unreliable-third-party-library-gitwalk.md`) to ensure `.gitignore` rules are respected.
-   [ ] **CREATE** `tests/integration/adapters/outbound/test_system_environment_inspector.py`
    -   Write a simple test to ensure `get_environment_info` returns a dictionary with the expected keys and non-empty string values.
-   [ ] **EDIT** `tests/integration/adapters/outbound/test_file_system_adapter.py`
    -   Add integration tests for the new `path_exists`, `create_directory`, and `write_file` methods.
    -   Update the tests for `read_file` to assert that it raises the correct exceptions on failure.
-   [ ] **CREATE** `tests/acceptance/test_context_command.py`
    -   Create a new acceptance test that runs `teddy context` as a subprocess.
    -   **Scenario 1 (First Run):** Test that the command creates the `.teddy` directory and default files.
    -   **Scenario 2 (Existing Context):** Test that the command correctly reads file paths from both `context.json` and `permanent_context.txt` and includes their content in the output.
    -   **Scenario 3 (Missing File):** Test that the command runs successfully and includes a "not found" message when a file listed in the context does not exist.
