# Slice: Hanging Command Management

- **Status:** Planned
- **Milestone:** N/A (Fast-Track)
- **Specs:** N/A

## 1. Business Goal
To prevent the TeDDy CLI from hanging indefinitely when an AI agent accidentally executes a blocking command (e.g., waiting for interactive input or starting a foreground server). This slice implements a global execution timeout, ensures partial output is captured for debugging, and adds an explicit mechanism for the AI to intentionally start background processes.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Configurable Global Timeout [✓]
When the `TeDDy` CLI initializes, the `YamlConfigAdapter` should load a default execution timeout from the configuration file.

#### Deliverables
- [✓] Add `execution.default_timeout_seconds` to `.teddy/config.yaml` (default to 30 seconds).
- [✓] Update `IConfigService` and `YamlConfigAdapter` to expose this property.
- [✓] Update `ExecutionOrchestrator` or `ShellAdapter` to retrieve and use this timeout during `EXECUTE` actions.

#### Implementation Notes
- Enhanced `YamlConfigAdapter` to support dot-notation for nested key lookups (e.g., `execution.default_timeout_seconds`).
- Updated `IShellExecutor` and `ShellAdapter` to accept an optional `timeout` parameter.
- Updated `ActionFactory` to inject `IConfigService` and automatically provide the global default timeout to shell actions if not explicitly overridden.

### Scenario 2: Command Timeout with Partial Output [✓]
When a shell command exceeds the configured timeout threshold, the process must be killed, and the partial output generated before the termination must be returned to the AI.

#### Deliverables
- [✓] Update `ShellAdapter`'s `subprocess.run` call to include the `timeout` parameter.
- [✓] Catch `subprocess.TimeoutExpired`.
- [✓] Extract `e.stdout` and `e.stderr`. **Critical:** Decode these bytes to strings using `.decode('utf-8', errors='replace')`, as the exception properties contain raw bytes even if `text=True` was passed to `run()`.
- [✓] Return a `ShellOutput` object with a non-zero exit code (e.g., 124, the standard Linux timeout exit code).
- [✓] Prepend or append a clear warning to the output text indicating: `[ERROR: Command timed out after X seconds]`.

#### Implementation Notes
- Updated `ShellAdapter._run_subprocess` to catch `subprocess.TimeoutExpired`.
- Implemented robust decoding of partial `stdout` and `stderr` from the exception, handling both `bytes` and `str` types (for cross-Python version stability).
- Mandated return of exit code `124` (standard Linux `timeout` code) when a process is killed due to timeout.
- Partial output is preserved and prepended with a clear warning message in the `stdout` field of the `ShellOutput`.

### Scenario 3: Intentional Background Execution [✓]
When the AI specifies that a command should run in the background, the executor should start the process and immediately return success without waiting for it to complete.

#### Deliverables
- [✓] Update the `ExecuteAction` domain model (`src/teddy_executor/core/domain/models/plan.py`) to include a `background: bool = False` field.
- [✓] Update `MarkdownPlanParser` (`src/teddy_executor/core/services/action_parser_strategies.py`) to extract the `- **Background:** [true|false]` parameter from the `EXECUTE` block metadata.
- [✓] Update `ShellAdapter` to check the `background` flag. If true, use `subprocess.Popen` directly (without calling `.wait()` or `communicate()`) and immediately return a successful `ShellOutput`.
- [✓] The `ShellOutput.stdout` must contain a clear, formatted message explicitly stating the Process ID (PID) of the detached process (e.g., `[SUCCESS: Background process started with PID 12345]`). This allows the AI to manage the lifecycle and terminate it in subsequent plans.
- [✓] Update `docs/project/specs/plan-format.md` to document the new `Background` parameter under the `EXECUTE` action section.

#### Implementation Notes
- Enhanced `MarkdownPlanParser` to extract and booleanize the `Background` metadata parameter for `EXECUTE` actions.
- Updated `ActionFactory` to propagate the `background` parameter through the service layer.
- Updated `ShellAdapter` to use `subprocess.Popen` with `start_new_session=True` for background execution, effectively detaching the process from the CLI's lifecycle.
- Implemented success reporting that includes the PID of the started background process.

### Scenario 4: Explicit Timeout Override
When the AI knows a command will legitimately take longer than the global default (e.g., a large test suite) but still needs to capture its output synchronously, it can explicitly override the timeout for that specific action.

#### Deliverables
- [ ] Update the `ExecuteAction` domain model (`src/teddy_executor/core/domain/models/plan.py`) to include a `timeout: Optional[int] = None` field.
- [ ] Update `MarkdownPlanParser` to extract the `- **Timeout:** [integer]` parameter from the `EXECUTE` block metadata.
- [ ] Update `ExecutionOrchestrator` to pass this specific timeout (if provided) to the `ShellAdapter`, falling back to the global configuration otherwise.
- [ ] Update `docs/project/specs/plan-format.md` to document the new `Timeout` parameter.

## 3. Architectural Changes
- **Configuration:** `yaml_config_adapter.py`
- **Domain:** `plan.py` (`ExecuteAction` data class)
- **Services:** `action_parser_strategies.py` (Parsing logic)
- **Adapters:** `shell_adapter.py` (Timeout handling, Byte decoding, `Popen` backgrounding)
- **Documentation:** `plan-format.md`
