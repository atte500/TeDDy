# Spec: Test Suite Rebalancing

**Status:** `Draft`

## 1. The Problem Space (The "Why")

### 1.1. Problem Statement

The current test suite is heavily weighted towards acceptance tests. While providing high confidence, this "inverted pyramid" has several drawbacks:
-   **Slow Feedback Loop:** Acceptance tests are inherently slower to run than unit or integration tests.
-   **High Maintenance Cost:** End-to-end tests can be brittle and require more effort to write and maintain.
-   **Inappropriate Level of Detail:** Some acceptance tests are focused on verifying the logic of a single component or action, a task better suited for a lower-level test.

### 1.2. Goal

The goal of this initiative is to refactor the test suite to follow a traditional, balanced "test pyramid" structure. This will improve the speed, maintainability, and overall quality of our test suite. The desired structure is:
1.  **A broad base of fast Unit Tests.**
2.  **A smaller set of focused Integration Tests.**
3.  **A minimal number of critical end-to-end Acceptance Tests.**

## 2. Proposed High-Level Strategy

This refactoring will be approached in two distinct phases.

### Phase 1: Migrate "Single-Action" Acceptance Tests to Integration Tests

We will identify acceptance tests that primarily validate the behavior of a single, isolated action (e.g., `CREATE`, `EDIT`). These will be migrated to integration tests that call the `ExecutionOrchestrator` service directly, using mocks for external boundaries like the file system. The slower, more complex acceptance test will then be deleted.

### Phase 2: Consolidate Critical User-Workflow Acceptance Tests

The remaining acceptance tests will be reviewed and consolidated to focus exclusively on verifying complete, critical user workflows (e.g., interactive prompts, diff previews, CLI flag combinations). The aim is to reduce the total number of acceptance tests while increasing the value and focus of those that remain.

---

## 3. The Solution Space (The "What")

### 3.1. Proposed Solution: Core Logic Integration Tests

To implement Phase 1, we will replace single-action acceptance tests with a new type of test: a **Core Logic Integration Test**.

**Definition:**
This test pattern verifies the integration between the `ExecutionOrchestrator` and the `ActionDispatcher`, ensuring that a given `ActionData` object is correctly routed to the appropriate outbound port (e.g., `IFileSystemManager`, `IShellExecutor`). It operates at the service layer, bypassing the CLI, parser, and report formatter.

**Benefits:**
*   **Speed:** These tests are significantly faster as they don't involve the overhead of `CliRunner` or filesystem I/O.
*   **Focus:** They test one thing well: "Does the orchestrator correctly handle this action?"
*   **Maintainability:** Asserting on mocked adapter calls is more direct and less brittle than parsing CLI output or checking filesystem state.

### 3.2. Canonical Migration Example

We will use `test_execute_markdown_plan_happy_path` (which tests the `CREATE` action) from `test_markdown_plans.py` as our model.

#### **Before: Acceptance Test Pattern**
```python
# From: tests/acceptance/test_markdown_plans.py

def test_execute_markdown_plan_happy_path(monkeypatch, tmp_path: Path):
    # 1. Arrange: Build a full Markdown string and set up a real temp directory.
    file_name = "hello.txt"
    plan_content = MarkdownPlanBuilder("Test").add_action(
        "CREATE",
        params={"File Path": f"[{file_name}](/{file_name})"},
        content_blocks={"": ("text", "Hello, world!")},
    ).build()

    # 2. Act: Run the full CLI application.
    result = run_execute_with_plan_content(monkeypatch, plan_content, tmp_path)

    # 3. Assert: Check exit codes, real filesystem state, and parsed CLI output.
    assert result.exit_code == 0
    assert (tmp_path / file_name).exists()
    report = parse_markdown_report(result.stdout)
    assert report["run_summary"]["Overall Status"] == "SUCCESS"
```

#### **After: Proposed Integration Test Pattern**
```python
# To: tests/integration/core/services/test_action_dispatch_logic.py (New File)

from teddy_executor.core.domain.models import Plan, ActionData, RunStatus

def test_create_action_is_dispatched_to_filesystem(container, mock_fs):
    # 1. Arrange: Build a domain-level Plan object.
    #    The container fixture provides all mocked dependencies.
    plan = Plan(
        title="Test Plan",
        actions=[
            ActionData(
                type="CREATE",
                params={"path": "hello.txt", "content": "Hello, world!"},
            )
        ],
    )
    orchestrator = container.resolve(RunPlanUseCase)

    # 2. Act: Directly invoke the core service.
    report = orchestrator.execute(plan=plan, interactive=False)

    # 3. Assert: Check the DTO response and that the correct mock was called.
    assert report.run_summary.status == RunStatus.SUCCESS
    mock_fs.create_file.assert_called_once_with(
        path="hello.txt", content="Hello, world!"
    )
```

### 3.3. Comprehensive Phase 1 Migration Checklist

The following is a complete list of all acceptance tests that have been identified as candidates for migration to Core Logic Integration Tests. Upon successful migration of all tests within a file, the original acceptance test file will be deleted.

#### `tests/acceptance/test_markdown_plans.py`
- [x] `test_execute_markdown_plan_happy_path` (CREATE action)
- [x] `test_markdown_edit_action` (EDIT action)
- [x] `test_markdown_execute_action` (EXECUTE action)
- [x] `test_markdown_read_action` (READ action)
- [x] `test_markdown_invoke_action` (INVOKE action)

## Implementation Summary

### Work Completed
- Successfully migrated all test cases from `tests/acceptance/test_markdown_plans.py` to a new integration test suite `tests/integration/core/services/test_action_dispatch_logic.py`.
- Established a module-level fixture for the `ExecutionOrchestrator` in integration tests, ensuring consistent DI setup.
- Deleted the redundant `tests/acceptance/test_markdown_plans.py` file.
- Verified that the rebalanced suite maintains 90% coverage and all tests pass.

### Refactoring & Observations
- **Mock Wrapping:** Discovered that `ActionFactory` wraps adapter methods in a local function. Integration tests must capture the original mock method (e.g., `original_execute = mock_shell.execute`) *before* the factory is invoked if they wish to perform assertions on it.
- **Contract Clarity:** Confirmed the exact parameter structure expected by the `ActionDispatcher` for `CREATE` and `EDIT` actions, ensuring the integration tests accurately simulate the system's internal data flow.

#### `tests/acceptance/test_create_file_action.py`
- [x] `test_create_file_happy_path`

#### `tests/acceptance/test_edit_action.py`
- [x] `test_edit_action_happy_path`

#### `tests/acceptance/test_walking_skeleton.py`
- [ ] `test_successful_execution` (EXECUTE action)
- [ ] `test_failed_execution` (EXECUTE action failure case)

#### `tests/acceptance/test_prompt_action.py`
- [ ] `test_prompt_action_successful`
- [ ] `test_prompt_action_multiline_editor`

#### `tests/acceptance/test_progress_logging.py`
*Note: These tests verify logging output, which is a side effect of the CLI layer. They may need to be adapted or moved to a different testing level.*
- [ ] `test_progress_logging_success` (READ action)
- [ ] `test_progress_logging_failure` (EXECUTE action)
- [ ] `test_progress_logging_execute_stdout` (EXECUTE action)

#### `tests/acceptance/test_report_enhancements.py`
*Note: These tests verify the final Markdown report format. The logic for this is in `MarkdownReportFormatter`, which should have its own unit tests. These acceptance tests can likely be replaced by unit tests.*
- [ ] `test_prompt_report_omits_prompt`
- [ ] `test_invoke_report_omits_details`
- [ ] `test_dynamic_language_in_code_blocks` (READ action)
