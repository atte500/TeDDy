# Vertical Slice: EXECUTE Action Refactor

## 1. Business Goal
To make the `EXECUTE` action more robust and less prone to parsing errors by explicitly separating environment setup and failure handling from the core command.

## 2. Acceptance Criteria

### Scenario: EXECUTE with Setup and Allow Failure
**Given** a plan with an `EXECUTE` action containing:
- `Setup: export FOO=bar && cd src`
- `Allow Failure: true`
- A command `ls`
**When** the plan is executed
**Then** the command `ls` should be executed within the context of the `Setup` commands
**And** if `ls` returns a non-zero exit code, the execution should continue to the next action.

### Scenario: Core Command Validation
**Given** an `EXECUTE` action
**When** the core command block contains any chaining operators (`&&`, `;`, `||`, `|`, `&`)
**Then** validation must fail with a clear "Command chaining is not allowed" message.

**When** the core command block starts with `cd ` or `export `
**Then** validation must fail, instructing the user to move these to the `Setup:` parameter.

### Scenario: Empty Command
**When** an `EXECUTE` action has an empty core command block
**Then** validation must fail.

## 3. User Showcase
1. Create a plan with an `EXECUTE` action that uses `Setup: export TEST_VAR=hello` and a command `echo $TEST_VAR`.
2. Run `teddy execute`.
3. Verify the output correctly prints `hello`.
4. Create an action with `Allow Failure: true` and a command that fails (e.g., `exit 1`).
5. Verify that `teddy` generates a report but does not halt execution for subsequent steps.

## 4. Architectural Changes
- **Parser (`src/teddy_executor/core/services/action_parser_strategies.py`):**
    - Update `parse_execute_action` to extract `Setup` and `Allow Failure` from metadata.
    - **Remove** the call to `extract_posix_headers` and the corresponding logic that strips `cd`/`export` from the raw command.
- **Validator (`src/teddy_executor/core/services/validation_rules/execute.py`):**
    - Simplify `_check_for_disallowed_chaining` and `_check_for_multiple_commands`.
    - **Strict Mode:** Forbid ALL chaining operators (`&&`, `||`, `;`, `|`, `&`) in the core command block without exception.
    - Add a check to explicitly forbid `cd` and `export` at the start of the core command.
    - Add a check for empty commands.
- **Orchestrator (`src/teddy_executor/core/services/execution_orchestrator.py`):**
    - In the `execute` loop, check `action.params.get("allow_failure")` (normalize string "true" to boolean).
    - If a failure occurs but `allow_failure` is true, do not set `halt_execution = True`.

## 5. Deliverables
- [ ] Updated `MarkdownPlanParser` for new `EXECUTE` metadata.
- [ ] Simplified `ExecuteActionValidator` with stricter core command rules.
- [ ] Updated `ExecutionOrchestrator` flow control.
- [ ] Passing unit and acceptance tests for the new format.
