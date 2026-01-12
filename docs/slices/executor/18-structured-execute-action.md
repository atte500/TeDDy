**Status:** Implemented

# Vertical Slice: Structured `execute` Action

## Business Goal

To refactor the `execute` action to be a stateless, declarative, and cross-platform compatible command. This change shifts the responsibility of handling execution context (like working directory and environment variables) from the AI planner (which previously had to generate fragile, shell-specific command strings) to the `teddy` executor itself. This makes plans more robust, readable, and portable across Windows, macOS, and Linux.

## Acceptance Criteria (Scenarios)

### Scenario 1: Simple Command Execution
**Given** a plan with a simple `execute` action
**When** the plan is executed
**Then** the command should run successfully in the current working directory.

### Scenario 2: Command with a Custom Working Directory
**Given** a plan with an `execute` action specifying a `cwd`
**When** the plan is executed
**Then** the command should run successfully within the specified directory.

### Scenario 3: Command with Environment Variables
**Given** a plan with an `execute` action specifying an `env` map
**When** the plan is executed
**Then** the command should run successfully with the specified environment variables set for its process.

### Scenario 4: Command with Both `cwd` and `env`
**Given** a plan with an `execute` action specifying both `cwd` and `env`
**When** the plan is executed
**Then** the command should run successfully in the specified directory with the specified environment variables.

### Scenario 5: Backwards Compatibility (Simple String Command)
**Given** a plan where the `execute` action is a simple string (old format)
**When** the plan is executed
**Then** the executor should interpret it as a command with no `cwd` or `env` and run it successfully.

### Scenario 6: Attempting to Use an Unsafe `cwd` Path
**Given** a plan with an `execute` action where `cwd` is an absolute path (e.g., `/etc/`, `C:\Users`)
**Or** the `cwd` path attempts to traverse outside the project root (e.g., `../../elsewhere`)
**When** the plan is executed
**Then** the action must fail with a clear error message before the command is ever run.

### Concrete Examples for AI Planner

Here are the specific YAML formats the AI planner should generate for each scenario.

-   **`cwd` (Working Directory):** This path must be a **relative path** that resolves to a directory *within* the project's root. The executor will enforce this security boundary.
    -   **Rule:** The `teddy` executor **must** validate this path. It will reject and fail the action if the path is absolute or attempts to escape the project directory (e.g., via `../`).
    -   **Rationale:** This "sandbox" ensures that an AI-generated plan cannot execute commands in sensitive system locations, making the executor a fundamentally safe tool.
    -   **Naming:** We use the name `cwd` to align directly with the terminology of Python's underlying `subprocess` module.
-   **`env` (Environment Variables):** This is a simple map of key-value string pairs that will be set for the duration of the command.

#### Scenario 1: Simple Command Execution
The AI generates a standard `execute` action. The command is run from the current directory.
```yaml
- action: execute
  command: "ls -la"
```

#### Scenario 2: Command with a Custom Working Directory
The `cwd` key is used to specify a relative path. The `poetry run pytest` command will be executed inside the `packages/executor` directory.
```yaml
- action: execute
  command: "poetry run pytest"
  cwd: "packages/executor"
```

#### Scenario 3: Command with Environment Variables
The `env` key provides a map of variables. The Python script will have access to `MY_API_KEY` and `MODE`.
```yaml
- action: execute
  command: "python my_script.py"
  env:
    MY_API_KEY: "12345-abcde"
    MODE: "production"
```

#### Scenario 4: Command with Both `cwd` and `env`
The keys can be combined. The test suite is run within the `packages/executor` directory, with a specific database URL set as an environment variable.
```yaml
- action: execute
  command: "poetry run pytest"
  cwd: "packages/executor"
  env:
    TEST_DATABASE_URL: "sqlite:///test.db"
```

#### Scenario 5: Backwards Compatibility (Simple String Command)
To support older plans, the executor will still accept a simple string. This is treated as a command with no `cwd` or `env` specified. The AI planner should prefer the structured format for all new plans.
```yaml
- action: execute
  command: "echo 'This still works'"
```

## Architectural Changes

-   **Domain Model:**
    -   Update the `ExecuteAction` data class in the domain model to include optional `cwd: Optional[str]` and `env: Optional[Dict[str, str]]` attributes.
-   **Application Service:**
    -   Update the `ActionFactory` (or `PlanService`) to parse both old and new formats for the `execute` action.
    -   **Crucially, the `PlanService` will be updated to include new validation logic. It must verify that the `cwd` path is not absolute and does not traverse outside the current project directory before executing the action.**
-   **Outbound Port:**
    -   Modify the `IShellExecutor` port. The `execute` method signature will be changed from `execute(command: str)` to `execute(command: str, cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> Tuple[int, str, str]`.
-   **Outbound Adapter:**
    -   Update the `ShellAdapter` to implement the new `IShellExecutor` interface. It will use Python's `subprocess` module, passing the `cwd` and `env` arguments to it directly to ensure cross-platform execution.

## Interaction Sequence

1.  The `PlanService` receives the parsed YAML plan.
2.  For each `execute` action, the `ActionFactory` determines if the action is in the legacy (string) or new (structured map) format.
3.  The `ActionFactory` creates an `ExecuteAction` domain object, populating the `command`, `cwd`, and `env` fields.
4.  The `PlanService` **validates the `cwd` path** from the `ExecuteAction` object. If the path is unsafe (absolute or escapes the project root), the service immediately fails the action and moves to the next step in the plan.
5.  If the path is valid, the `PlanService` invokes the `execute` method on its `IShellExecutor` dependency, passing the attributes from the `ExecuteAction` object.
6.  The `ShellAdapter` (implementing `IShellExecutor`) receives the command, `cwd`, and `env`.
6.  The `ShellAdapter` uses the `subprocess.run` function, passing the `command`, `cwd`, and `env` parameters to it.
7.  The result of the subprocess (return code, stdout, stderr) is captured and returned up the call stack.

## Scope of Work

This section provides the detailed, file-by-file checklist for the developer to implement this slice.

### Core Domain
-   **File:** `packages/executor/src/teddy_executor/core/domain/actions.py` (or similar)
    -   [ ] Modify the `ExecuteAction` dataclass to include `cwd: Optional[str] = None` and `env: Optional[Dict[str, str]] = None`.

### Outbound Port
-   **File:** `packages/executor/src/teddy_executor/core/ports/outbound/shell_executor.py` (or similar)
    -   [ ] Rename the abstract class from `ShellExecutor` to `IShellExecutor`.
    -   [ ] Rename the abstract method from `run` to `execute`.
    -   [ ] Update the `execute` method signature to `execute(self, command: str, cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> CommandResult`.

### Application Service
-   **File:** `packages/executor/src/teddy_executor/core/services/plan_service.py` (or similar)
    -   [ ] Update the `__init__` method to type-hint the `shell_executor` dependency as `IShellExecutor`.
    -   [ ] In the `_handle_execute` method (or equivalent handler for `ExecuteAction`):
        -   [ ] **Implement Validation:** Add logic to validate the `action.cwd`. It must fail if the path is absolute or resolves outside the project's root directory.
        -   [ ] **Update Port Call:** Modify the call to the shell executor to pass the new parameters: `self.shell_executor.execute(command=action.command, cwd=action.cwd, env=action.env)`.
-   **File:** `packages/executor/src/teddy_executor/core/services/action_factory.py` (or similar)
    -   [ ] Modify the `_parse_execute` method to handle both the legacy string format and the new structured map format (`{ "command": "...", "cwd": "...", "env": {...} }`).

### Outbound Adapter
-   **File:** `packages/executor/src/teddy_executor/adapters/outbound/shell_adapter.py` (or similar)
    -   [ ] Update `ShellAdapter` to implement the `IShellExecutor` interface.
    -   [ ] Rename the `run` method to `execute`.
    -   [ ] Update the `execute` method signature to match the port.
    -   [ ] Pass the `cwd` and `env` parameters directly to the `subprocess.run()` call.

### Testing
-   **File:** `packages/executor/tests/unit/...`
    -   [ ] Update any unit tests for `PlanService` to provide a mock `IShellExecutor` that respects the new method signature.
    -   [ ] Add new unit tests for the `PlanService` to specifically verify the `cwd` validation logic (test for absolute paths, test for `../` traversal).
-   **File:** `packages/executor/tests/acceptance/test_execute_action.py` (or create a new one)
    -   [ ] Add acceptance tests corresponding to each scenario defined in the `Acceptance Criteria`, including `cwd` and `env` usage.
    -   [ ] Add an acceptance test for the unsafe `cwd` path scenario to ensure the action fails correctly.
    -   [ ] Add an acceptance test to ensure backwards compatibility with the simple string format for an `execute` action.
