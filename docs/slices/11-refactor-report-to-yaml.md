# Vertical Slice 11: Refactor Execution Report to Pure YAML

### 1. Business Goal
To improve the robustness, testability, and machine-readability of the application by standardizing the final execution report to a pure YAML format. This removes ambiguity from the primary data contract between the executor and its consumer (the AI agent) and makes acceptance testing significantly more reliable.

### 2. Acceptance Criteria (Scenarios)

**Scenario 1: Verify `create_file` Action with YAML Output**
*   **Given** a plan with a `create_file` action.
*   **When** the TeDDy executor runs the plan.
*   **Then** the output printed to the console is a valid YAML document.
*   **And** the parsed YAML contains an `action_logs` list where the `create_file` action result is correctly represented.

**Scenario 2: Verify `execute` Action Failure with YAML Output**
*   **Given** a plan with an `execute` action that fails (e.g., `exit 1`).
*   **When** the TeDDy executor runs the plan.
*   **Then** the output printed to the console is a valid YAML document.
*   **And** the parsed YAML has a `run_summary.status` of `FAILURE`.
*   **And** the `action_logs` entry for the `execute` action has a `status` of `FAILURE` and includes the command's `error` output.

*(Note: Similar acceptance criteria apply to all existing action types: `read`, `edit`, `chat_with_user`.)*

### 3. Interaction Sequence
1.  The `PlanService` completes the execution of a plan and returns the `ExecutionReport` domain object.
2.  The `main` function in `src/teddy/main.py` receives the `ExecutionReport`.
3.  It passes the report to a refactored `format_report_as_yaml` function (previously `format_report_as_markdown`) located in the `CliInboundAdapter`.
4.  The formatter serializes the `ExecutionReport` object into a well-structured YAML string, following the contract defined in the `README.md`.
5.  The `main` function prints the resulting YAML string to standard output.

### 4. Scope of Work (Components)

*   [x] **Adapter:** `MODIFY` `src/teddy/adapters/inbound/cli_formatter.py` to replace the Markdown formatting logic with YAML serialization logic. The `format_report_as_markdown` function will be renamed to `format_report_as_yaml`.
*   [x] **Framework Integration:** `MODIFY` `src/teddy/main.py` to call the renamed `format_report_as_yaml` function.
*   [x] **Testing:** `MODIFY` all existing acceptance tests in `tests/acceptance/` to parse the new YAML output instead of performing string or regex matching on Markdown. The tests' core assertions about action success/failure will remain, but the method of verifying the output will be completely changed.
