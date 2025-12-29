# Vertical Slice 13: Implement `context` Command

## 1. Business Goal

To provide the AI agent with a comprehensive, machine-readable snapshot of the project's current state. This command is crucial for enabling the AI to generate accurate, context-aware plans by giving it access to the repository structure, key configuration files, and the contents of any relevant source files.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: First-time initialization
- **Given** the `.teddy` directory does not exist
- **When** the user runs `teddy context`
- **Then** a directory named `.teddy` is created in the current working directory
- **And** a file named `.teddy/context.yaml` is created and is empty
- **And** a file named `.teddy/permanent_context.yaml` is created
- **And** the `.teddy/permanent_context.yaml` file contains a default list of files: `README.md`, `docs/ARCHITECTURE.md`, and `repotree.log`
- **And** a file named `.teddy/.gitignore` is created with the content `*` to prevent accidental commits of context files.

### Scenario 2: Standard execution
- **Given** the `.teddy` directory and its files exist
- **And** the project has a root `.gitignore` file
- **When** the user runs `teddy context`
- **Then** a file named `repotree.log` is created or overwritten in the root directory
- **And** the `repotree.log` file contains a textual representation of the file tree, ignoring all paths specified in the root `.gitignore`
- **And** the command's standard output contains the following, clearly delineated sections:
    1.  Operating System & Terminal Information
    2.  The content of the root `.gitignore` file
    3.  The content of `.teddy/context.yaml`
    4.  The content of `.teddy/permanent_context.yaml`
    5.  The content of every file listed in both `context.yaml` and `permanent_context.yaml`

### Scenario 3: Handling missing files
- **Given** `.teddy/context.yaml` lists a file named `non_existent_file.py`
- **When** the user runs `teddy context`
- **Then** the output for the content of `non_existent_file.py` clearly indicates that the file was not found.

## 3. Data Contracts

### Context YAML Files

The context system relies on two YAML files located in the `.teddy/` directory. Both files share the same simple format: a YAML list of file paths.

#### `.teddy/context.yaml`
This file is intended to be managed by the AI. It can add or remove files from this list to focus its attention on specific parts of the codebase for a given task.

```yaml
# Files for the current task. This file is managed by the AI.
- src/teddy/cli.py
- tests/acceptance/test_cli.py
```

#### `.teddy/permanent_context.yaml`
This file is for the user to manage. The AI will not edit this file. The `context` command will create it with sensible defaults on its first run. The user can add files here that should *always* be included in the context snapshot.

```yaml
# Permanent context files. This file is managed by the user.
- README.md
- docs/ARCHITECTURE.md
- repotree.log
- pyproject.toml
```

## 4. Interaction Sequence

1.  User executes `teddy context` in their terminal.
2.  The `CLI` (Inbound Adapter) receives the command and its arguments.
3.  The `CLI` invokes the `ContextService` (Application Service) via the `IGetContextUseCase` (Inbound Port).
4.  The `ContextService` orchestrates the gathering of information:
    a.  It calls the `IFileSystemManager` (Outbound Port) to ensure the `.teddy` directory and its default files (`context.yaml`, `permanent_context.yaml`, `.gitignore`) exist, creating them if necessary.
    b.  It calls the `IRepoTreeGenerator` (Outbound Port) to scan the filesystem (respecting `.gitignore`) and generate the repository tree string.
    c.  It calls the `IFileSystemManager` to write the generated tree to `repotree.log`.
    d.  It calls the `IEnvironmentInspector` (Outbound Port) to get OS and terminal details.
    e.  It calls the `IFileSystemManager` to read the contents of the root `.gitignore`, both context YAML files, and every file path listed within them. It tracks any files that are not found.
    f.  It aggregates all collected data (OS info, file contents, repo tree, etc.) into a `ProjectContext` (Domain Object).
5.  The `ContextService` returns the `ProjectContext` object to the `CLI`.
6.  The `CLI` formats the `ProjectContext` data into a single, structured string and prints it to standard output.

## 5. Activation & Wiring Strategy

In `src/teddy/cli.py`, a new command function decorated with `@app.command()` will be created for `context`. This function will instantiate and call the `ContextService`, which in turn will be wired with concrete adapter implementations for `IFileSystemManager`, `IRepoTreeGenerator`, and `IEnvironmentInspector`.

## 6. Scope of Work (Implementation)

This checklist outlines the source code and test files to be created or modified by the developer.

### Hexagonal Core (`src/teddy/core/`)
- [ ] **Domain:** `MODIFY src/teddy/core/domain/models.py`
    - Add `ProjectContext` aggregate and `FileContent` value object.
- [ ] **Ports:** `MODIFY src/teddy/core/ports/inbound.py`
    - Add `IGetContextUseCase` protocol.
- [ ] **Ports:** `MODIFY src/teddy/core/ports/outbound.py`
    - Add `IRepoTreeGenerator` and `IEnvironmentInspector` protocols.
    - Add `path_exists`, `create_directory`, and `write_file` methods to the `IFileSystemManager` protocol.
- [ ] **Services:** `CREATE src/teddy/core/services/context_service.py`
    - Implement the `ContextService` class which implements `IGetContextUseCase`.

### Adapters (`src/teddy/adapters/`)
- [ ] **Outbound:** `CREATE src/teddy/adapters/outbound/repo_tree_generator.py`
    - Implement the `LocalRepoTreeGeneratorAdapter`.
- [ ] **Outbound:** `CREATE src/teddy/adapters/outbound/system_environment_inspector.py`
    - Implement the `SystemEnvironmentInspectorAdapter`.
- [ ] **Outbound:** `MODIFY src/teddy/adapters/outbound/file_system_adapter.py`
    - Implement the new methods from the `IFileSystemManager` port.

### Framework & Wiring (`src/teddy/`)
- [ ] **CLI:** `MODIFY src/teddy/cli.py`
    - Add the new `context` command using `@app.command()`.
    - Instantiate and wire all the new services and adapters for this command.
- [ ] **CLI Formatter:** `MODIFY src/teddy/cli_formatter.py`
    - Add a `format_project_context` function.

### Tests (`tests/`)
- [ ] **Unit:** `MODIFY tests/unit/core/services/test_context_service.py` (or create)
    - Test `ContextService` logic using mocks for all outbound ports.
- [ ] **Integration:** `CREATE tests/integration/adapters/outbound/test_repo_tree_generator.py`
    - Test the repo tree adapter against a temporary directory structure.
- [ ] **Acceptance:** `MODIFY tests/acceptance/test_cli.py`
    - Add end-to-end tests for the `teddy context` command.
