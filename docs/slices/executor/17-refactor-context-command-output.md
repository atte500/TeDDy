**Status:** Implemented

# Vertical Slice: Refactor `context` Command Output

## Business Goal

To improve the usability, consistency, and reliability of the `teddy context` command. This refactoring will standardize the output format, simplify the default configuration for new users, and remove intermediate file artifacts (`repotree.txt`), making the command more intuitive for users and more robust for AI consumption.

## Acceptance Criteria (Scenarios)

### Scenario 1: Standardized Output Format
- **Given** a project with a `.teddy/perm.context` file
- **When** the user runs the `teddy context` command
- **Then** the output to `stdout` MUST contain four distinct sections in this exact order: `# System Information`, `# Repository Tree`, `# Context Vault`, `# File Contents`.
- **And** the `# System Information` section MUST include the user's current `shell`.
- **And** the `# System Information` section MUST NOT include the `python_version`.

### Scenario 2: Simplified Default Configuration
- **Given** a project that does not have a `.teddy/perm.context` file
- **When** the user runs the `teddy context` command for the first time
- **Then** a new file `.teddy/perm.context` MUST be created.
- **And** the content of the newly created `.teddy/perm.context` file MUST ONLY contain `README.md` and `docs/ARCHITECTURE.md`, each on a new line.

### Scenario 3: Clean Context Vault Listing
- **Given** a `.teddy/perm.context` file and a `.teddy/temp.context` file
- **When** the user runs the `teddy context` command
- **Then** the `# Context Vault` section of the output MUST contain a simple, newline-delimited list of all file paths from both context files.
- **And** this section MUST NOT contain any markdown code fences or comments.

### Scenario 4: Direct Repository Tree Output
- **Given** a project repository
- **When** the user runs the `teddy context` command
- **Then** the repository tree structure MUST be printed directly under the `# Repository Tree` section.
- **And** the command MUST NOT create or modify a `repotree.txt` file in the local directory.

## Architectural Changes

-   **Port (Inbound):** `IGetContextUseCase` - The data transfer object returned by the use case may need to be updated to reflect the new, structured output.
-   **Service:** `ContextService` - The service will be updated to orchestrate the gathering of the new structured data (including shell info) and to manage the creation of the simplified default `perm.context` file.
-   **Adapter (Outbound):** `LocalRepoTreeGenerator` - This adapter will be modified to return the repository tree as a string, rather than writing it to a file.
-   **Adapter (Outbound):** `LocalFileSystemAdapter` - The logic for creating the default `.teddy/perm.context` file will be updated to write the new, simplified content.
-   **Adapter (Inbound):** `CLI Adapter` - This adapter will be responsible for formatting the structured data from the `ContextService` into the final, sectioned string output to `stdout`.

## Interaction Sequence

1.  The `CLI Adapter` receives the `context` command from the user.
2.  It invokes the `IGetContextUseCase.get_context()` method on the `ContextService`.
3.  The `ContextService` checks for the existence of `.teddy/perm.context`.
4.  If the file is missing, `ContextService` instructs the `LocalFileSystemAdapter` to create `.teddy/perm.context` with the simplified default content (`README.md` and `docs/ARCHITECTURE.md`).
5.  The `ContextService` calls the `SystemEnvironmentInspector` to get system information, including the user's shell.
6.  The `ContextService` calls the `LocalRepoTreeGenerator` to generate the repository tree directly as a string.
7.  The `ContextService` reads the file paths from all `.teddy/*.context` files.
8.  The `ContextService` instructs the `LocalFileSystemAdapter` to read the content of each file listed in the context vault.
9.  The `ContextService` aggregates all collected information (system info, repo tree string, vault paths, file contents) into a single data structure and returns it to the `CLI Adapter`.
10. The `CLI Adapter` takes this data structure and formats it into the final `stdout` string, prepending each section with the appropriate markdown header (`# System Information`, etc.).
11. The final formatted string is printed to the console.

## Scope of Work

### Core (Domain)
- **EDIT:** `packages/executor/src/teddy_executor/core/domain/models.py`
    - Define the new `ContextResult` data class to match the structure specified in `docs/contexts/executor/ports/inbound/get_context_use_case.md`.

### Core (Services)
- **EDIT:** `packages/executor/src/teddy_executor/core/services/context_service.py`
    - Update `ContextService.get_context()` to implement the new orchestration logic.
    - It must now check for `.teddy/perm.context` and call a method on the `file_system_manager` to create it if absent.
    - It must call the `repo_tree_generator` to get the tree as a string.
    - It must call the `environment_inspector` to get the `shell`.
    - It must assemble and return the new `ContextResult` DTO.

### Adapters (Outbound)
- **EDIT:** `packages/executor/src/teddy_executor/adapters/outbound/local_file_system_adapter.py`
    - Add a new method `create_default_context_file()` that creates `.teddy/perm.context` with the simplified content (`README.md\ndocs/ARCHITECTURE.md`).
- **EDIT:** `packages/executor/src/teddy_executor/adapters/outbound/local_repo_tree_generator.py`
    - Modify the `generate()` method to build the repository tree as a string in memory and return it, instead of writing to a file.
- **EDIT:** `packages/executor/src/teddy_executor/adapters/outbound/system_environment_inspector.py`
    - Modify `get_environment()` to include the user's `shell` (e.g., from the `SHELL` environment variable).

### Adapters (Inbound)
- **EDIT:** `packages/executor/src/teddy_executor/adapters/inbound/cli_formatter.py`
    - Update `format_project_context()` to accept the new `ContextResult` DTO.
    - Implement the four-section output format as specified in this slice's documentation.
    - Ensure `python_version` is excluded from the System Information section.
    - Ensure the Context Vault is a simple list of paths.
    - Ensure file contents are formatted with the special `ext` code fences.

### Tests
- **CREATE:** `packages/executor/tests/acceptance/test_context_command_refactor.py`
    - Create a new acceptance test file to verify all acceptance criteria for this slice.
    - **Test Case 1 (Standardized Output):** Verify that the `teddy context` output contains the four sections in order, includes the `shell`, and excludes the `python_version`.
    - **Test Case 2 (Default Config Creation):** In a clean temporary directory, run `teddy context`, and assert that `.teddy/perm.context` is created with the correct simplified content.
    - **Test Case 3 (Clean Vault & No repotree.txt):** Run `teddy context` and verify the `# Context Vault` section is a clean list and that no `repotree.txt` file is created.
