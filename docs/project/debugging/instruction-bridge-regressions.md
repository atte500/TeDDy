# MRE: Instruction Bridge Regressions
- **Status:** Resolved

## 1. Failure Context
Multiple tests are failing after the introduction of the Instruction Bridge (Scenario: Unified Instruction Bridge). Failures include `TypeError`, `AttributeError`, and assertion errors in prompts and reports.

## 2. Steps to Reproduce
1. Run full test suite: `poetry run pytest`.
2. Observe failures in:
   - `tests/suites/acceptance/test_change_preview_feature.py`
   - `tests/suites/integration/core/services/test_action_executor_integration.py`
   - `tests/suites/unit/core/services/test_action_executor.py`
   - `tests/suites/unit/core/services/test_orchestrator_interaction.py`
   - `tests/suites/acceptance/test_tui_instruction_bridge.py`
   - `tests/suites/acceptance/test_ui_mode_toggling.py`

## 3. Expected vs. Actual Behavior
### Return Type Mismatch
- **Expected:** `confirm_and_dispatch` return types are consistent across all call sites and tests.
- **Actual:** `TypeError: cannot unpack non-iterable ActionLog object` in `ExecutionOrchestrator` and `AttributeError` in unit tests.

### Prompt Content
- **Expected:** Tests should reflect the new `(y/n/m)` prompt.
- **Actual:** Tests assert `(y/n)` and fail.

### Report Content
- **Expected:** `## User Request` section appears in the report when a message is provided.
- **Actual:** Section is missing.

## 4. Relevant Code
- `src/teddy_executor/core/services/action_executor.py`
- `src/teddy_executor/core/services/execution_orchestrator.py`
- `src/teddy_executor/adapters/outbound/console_interactor.py`
- `src/teddy_executor/core/services/templates/execution_report.md.j2`

## 6. Root Cause Analysis
### 1. Port/Adapter Mismatch
The `IPlanReviewer.review_action` port was incorrectly returning a `bool`, which caused the `ConsolePlanReviewer` to drop the `user_request` string captured by the `UserInteractor`. This broke the instruction bridge whenever a reviewer was involved.

### 2. Variable Shadowing in Orchestrator
In `ExecutionOrchestrator._process_plan_actions`, the `message` variable captured from the reviewer was being immediately overwritten by an empty string returned from `ActionExecutor.confirm_and_dispatch(interactive=False)`.

### 3. Out-of-Sync Test Mocks
Several unit and integration tests used mocks that returned a single `ActionLog` or `bool`, which caused `TypeError` after the core services were updated to return `(ActionLog, str)` or `(bool, str)` to support the bridge.

### 4. Rigid AST Reporting
The `ParserReporting` logic hardcoded "backticks" for all code fence nodes, making it difficult to debug plans using tildes (e.g., when nesting backticks).

## 6. Proposed Fix

| Strategy | Pros | Cons | Regression Risk |
| :--- | :--- | :--- | :--- |
| **1. Full Alignment** (Recommended) | Explicit, typed data flow. Consistent with Instruction Bridge design. | Requires updating many test mocks and assertions. | Low - improves clarity. |
| **2. Side-Channel State** | Minimal test changes. | Brittle; violates stateless principles; hidden state. | Medium - race conditions. |

### Primary Recommendation: Strategy 1
Update all call sites and mocks to support the `(ActionLog, str)` return type. Synchronize all test assertions with the new `(y/n/m)` prompt. Clean up the `CliTestAdapter` duplication.

## 7. Implementation Notes
- **Port Alignment:** Updated `IPlanReviewer.review_action` to return `tuple[bool, str]`. Synchronized `ConsolePlanReviewer` and `TextualPlanReviewer` to return captured messages.
- **Orchestrator Fix:** Removed variable shadowing in `_process_plan_actions` and ensured that messages captured from either the reviewer or the executor are correctly prioritized and persisted to `plan.metadata["user_request"]`.
- **Test Harness:** Cleaned up `CliTestAdapter` to remove redundant shadowing of `subprocess.run`. Consolidated mock editor output logic into the `TEDDY_TEST_MOCK_EDITOR_OUTPUT` environment variable.
- **AST Labels:** Updated `ParserReporting.format_node_name` to dynamically detect delimiter type and count, providing clear labels like `Code Block (6 tildes)` in error reports.
- **Verification:** Verified that all 12 reported failing tests (Acceptance, Integration, Unit) now pass sequentially and in parallel.
