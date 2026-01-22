# Vertical Slice: Critical Bug Fixes

*   **Source Brief**: [Brief: CLI Refinements & Bug Fixes](../../briefs/05-cli-refinements-and-bug-fixes.md)

## 1. Business Goal

To improve the reliability and robustness of the `teddy` executor by fixing three critical bugs:
1.  Prevent YAML parsing errors for `execute` commands that contain unquoted colons.
2.  Ensure the `description` field from a plan is correctly included in the final execution report for better traceability.
3.  Extend the `read` action to support reading content directly from URLs.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Robust YAML Parsing

*   **Given** a `plan.yaml` file containing an `execute` action where the `command` string has a colon but is not quoted.
*   **When** the user executes the plan with `teddy`.
*   **Then** the plan is parsed and executed successfully without raising a `yaml.ScannerError`.

**Example:**
```yaml
# plan.yaml
actions:
  - action: execute
    description: "Run a specific pytest test."
    command: poetry -C packages/executor run pytest -k "test_action_failure_behavior:test_failure_report"
```

### Scenario 2: Description Field in Report

*   **Given** a `plan.yaml` where an action includes a `description` field.
*   **When** the user executes the plan with `teddy`.
*   **Then** the final YAML `ExecutionReport` includes the corresponding `description` field in that action's log.

**Example:**
```yaml
# plan.yaml
actions:
  - action: create_file
    description: "Create a dummy file."
    path: 'dummy.txt'
    content: 'hello'
```

**Expected Report Snippet:**
```yaml
...
report:
  ...
  action_logs:
    - status: SUCCESS
      action_type: create_file
      description: Create a dummy file. # This field must be present
      params:
        path: dummy.txt
        content: hello
...
```

### Scenario 3: Read from URL

*   **Given** a `plan.yaml` file with a `read` action whose `path` is a valid URL to an HTML page.
*   **When** the user executes the plan with `teddy`.
*   **Then** the action log in the `ExecutionReport` shows a `status` of `SUCCESS`.
*   **And** the `details` field of the action log contains the Markdown-converted content of the web page.

**Example:**
```yaml
# plan.yaml
actions:
  - action: read
    description: "Read content from example.com"
    path: "https://example.com"
```

## 3. Architectural Changes

The following components will require design modifications to implement this slice:

*   **Service:** `PlanParser`
*   **Domain Model:** `ExecutionReport`
*   **Service:** `ActionDispatcher`
*   **Service:** `ActionFactory` (specifically, its internal `ReadAction` handler)
*   **Composition Root:** `main.py`

## 4. Interaction Sequence

1.  The user invokes `teddy plan.yaml`.
2.  The `CLIAdapter` passes the raw YAML content to the `IRunPlanUseCase` (implemented by `ExecutionOrchestrator`).
3.  The `ExecutionOrchestrator` calls the `PlanParser` service.
4.  The `PlanParser` pre-processes the raw YAML string to wrap any unquoted, single-line values containing colons in double quotes, then safely parses it into a `Plan` object.
5.  The `ExecutionOrchestrator` iterates through the actions in the `Plan`.
6.  For each action, it calls `ActionDispatcher.dispatch_and_execute`, passing the full action data, including the `description`.
7.  The `ActionDispatcher` creates an `ActionLog` and ensures the `description` from the plan is populated in it.
8.  When dispatching a `read` action:
    a. The `ActionFactory`'s internal `ReadAction` handler, now injected with both `IFileSystemManager` and `IWebScraper`, examines the `path`.
    b. If the `path` starts with `http://` or `https://`, it delegates the call to the `IWebScraper` port.
    c. The `WebScraperAdapter` fetches the remote content and converts it to Markdown.
9.  The `ExecutionOrchestrator` collects all `ActionLog` objects and builds the final `ExecutionReport`.
10. The `CLIAdapter` formats and prints the report, which now correctly includes the `description` field for each action.

## 5. Scope of Work

This checklist guides the implementation of the three critical bug fixes for this slice in an "outside-in" TDD fashion.

### Task 1: Fix YAML Parsing

1.  **READ:** The updated design for the `PlanParser` service:
    *   [`docs/contexts/executor/services/plan_parser.md`](../../contexts/executor/services/plan_parser.md)
2.  **IMPLEMENT:** The YAML pre-processing logic in `PlanParser.parse` to handle unquoted colons in string values.
    *   _Location:_ `packages/executor/src/teddy_executor/core/services/plan_parser.py`

### Task 2: Add `description` to Report

1.  **READ:** The updated design for the `ExecutionReport` domain model:
    *   [`docs/contexts/executor/domain/execution_report.md`](../../contexts/executor/domain/execution_report.md)
2.  **IMPLEMENT:** Add the `description: Optional[str] = None` field to the `ActionLog` dataclass.
    *   _Location:_ `packages/executor/src/teddy_executor/core/domain/models/execution_report.py`
3.  **READ:** The updated design for the `ActionDispatcher` service:
    *   [`docs/contexts/executor/services/action_dispatcher.md`](../../contexts/executor/services/action_dispatcher.md)
4.  **IMPLEMENT:** Update `ActionDispatcher.dispatch_and_execute` to accept the full `ActionData` and pass the `description` field into the `ActionLog` it constructs.
    *   _Location:_ `packages/executor/src/teddy_executor/core/services/action_dispatcher.py`

### Task 3: Implement URL `read`

1.  **READ:** The updated design for the `ActionFactory`:
    *   [`docs/contexts/executor/services/action_factory.md`](../../contexts/executor/services/action_factory.md)
2.  **IMPLEMENT:** The required changes to support URL reading:
    *   Modify the `ReadAction` handler to accept both `IFileSystemManager` and `IWebScraper` via its constructor.
    *   Implement the logic in its `execute` method to check if the `path` is a URL and delegate to the appropriate adapter.
    *   Update the `ActionFactory` to inject both dependencies into the `ReadAction` handler.
    *   Update the composition root in `main.py` to provide the `WebScraperAdapter` to the `ActionFactory`.
    *   _Locations:_
        *   `packages/executor/src/teddy_executor/core/services/action_factory.py`
        *   `packages/executor/src/teddy_executor/main.py`
