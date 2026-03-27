# MRE: Systemic Hangs and Crashes in Session Orchestration

- **Status:** Resolved ✅
- **Reported Date:** 2026-03-27

## 1. Failure Context
Recent changes to implement "Tiered Message Resolution" and the "Unified Instruction Bridge" have resulted in systemic failures in the acceptance test suite `tests/suites/acceptance/test_session_management.py`.

- 5/6 tests fail.
- Primary failure mode: `Timeout (>5.0s)` from `pytest-timeout`.
- Secondary failure mode: `SystemExit(1)` or `AssertionError: assert 1 == 0`.
- Tracebacks point to `yaml.safe_load` (SessionPlanner) and `jinja2` rendering (MarkdownReportFormatter).

## 2. Steps to Reproduce
Run the acceptance tests for session management:
```shell
pytest tests/suites/acceptance/test_session_management.py -n 0
```

## 3. Expected vs. Actual Behavior
- **Expected:** Tests complete within seconds and pass.
- **Actual:** Multiple tests hang until the 5s timeout or exit with error code 1.

## 4. Relevant Code
- `src/teddy_executor/core/services/session_orchestrator.py`: Turn transition and execution loop.
- `src/teddy_executor/core/services/session_planner.py`: Telemetry display and metadata loading (`yaml.safe_load`).
- `src/teddy_executor/core/services/planning_service.py`: Plan generation and telemetry logging.
- `src/teddy_executor/adapters/inbound/session_cli_handlers.py`: CLI loop for `start` and `resume`.

## 5. Investigation Log
- `test_teddy_resume_executes_pending_plan`: PASSED (after adding loop break for non-interactive mode).
- `test_teddy_start_bootstraps_session`: TIMEOUT at `yaml.safe_load(str(content))` in `SessionPlanner.trigger_new_plan`.
- `test_teddy_resume_prompts_for_new_plan`: TIMEOUT in `jinja2` rendering during `handle_report_output`.
- `test_teddy_resume_continuous_loop`: FAIL (`SystemExit(1)`) likely due to mock side-effect exhaustion or loop termination logic.

## 6. Root Cause Analysis
1. **Redundant Jinja2 Compilation (Confirmed):** `IMarkdownReportFormatter` was registered as `transient`. Every resolution (twice per turn) triggered a full Jinja2 environment creation and template compilation. Under `pyfakefs`, this caused systemic hangs (>5s timeouts).
2. **Missing Loop Exit Condition (Confirmed):** `SessionCLIHandlers` loops indefinitely. `PlanningService` did not return a "Stop" signal on empty input, instead calling the LLM with empty messages. In tests, this exhausted mocks, causing `SystemExit(1)`.

## 7. Proposed Fix

| Strategy | Pros | Cons | Regression Risk |
| :--- | :--- | :--- | :--- |
| **Singleton & Cache** | Eliminates redundant compilation; significant speedup. | Templates cannot be updated without restart. | Low |
| **Graceful Exit Signal** | Prevents infinite loops; allows clean session termination. | Requires minor refactor of planning return types. | Low |
| **Defensive String Casting** | Prevents `yaml.safe_load` from attempting to parse raw mocks. | Minimal impact; already partially exists. | None |

**Primary Recommendation:** Implement both the Singleton/Cache for the formatter and the Exit Signal for the planning loop.

## 8. Implementation Notes
- Convert `IMarkdownReportFormatter` to `Scope.singleton`.
- Cache `Environment` and `Template` in `MarkdownReportFormatter` class attributes.
- `PlanningService.generate_plan` will return `(None, 0.0)` if `resolved_message` is empty.
- `SessionOrchestrator` and `SessionPlanner` will propagate the `None` result to terminate the CLI loop.
