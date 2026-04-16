# Bug: Generic Descriptions for Aborted Actions

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** N/A
- **Specs:** [report-format.md](../specs/report-format.md)

## Symptoms
When a plan execution fails at a specific step, subsequent steps are marked as aborted/skipped. In the resulting Execution Report, these aborted steps lose their original descriptions and are replaced with generic placeholders like "Execute Command" or "Research".

### Reproduction Steps
1. Create a plan with two actions:
   - `EXECUTE`: "Fail step" (command that returns non-zero).
   - `EXECUTE`: "Should keep this description".
2. Run the plan.
3. Observe the Execution Report.

**Expected:** The second action should be listed as aborted but keep the description "Should keep this description".
**Actual:** The second action is listed as "Execute Command".

## Context & Scope
*   **Regressing Commit:** Unknown
*   **Environmental Boundaries:** All platforms.
*   **Ruled Out:**
    *   TUI interaction (happens in headless execution too).

## Diagnostic Analysis
### Causal Model
1.  The `MarkdownPlanParser` parses the Markdown plan into `ActionData` objects, where the "description" is stored as a direct attribute.
2.  The `ExecutionOrchestrator` iterates through these actions.
3.  If an action fails, subsequent actions are passed to `ActionExecutor.handle_skipped_action`.
4.  `ActionExecutor.handle_skipped_action` calls `_create_intercepted_log`.
5.  **Faulty Step:** `_create_intercepted_log` creates a copy of `action.params` called `log_params` and adds the "Description" key to it, but then initializes the `ActionLog` with the original `action.params` (which lacks the description).
6.  The `MarkdownReportFormatter` (using Jinja2) renders the report.
7.  The template `execution_report.md.j2` fails to find "description" or "Description" in the `ActionLog.params` and falls back to generic strings like "Execute Command".

### Discrepancies
*   (resolved: `_create_intercepted_log` uses the wrong variable `action.params` when it should use the enriched `log_params`. Confirmed by MRE output showing generic "Execute Command" for a skipped action with a specific description.)

### Investigation History
- **2026-04-16:** Confirmed bug via static analysis and MRE `debug/repro_generic_description.py`. The `ActionExecutor._create_intercepted_log` method enriches `log_params` but passes `action.params` to the `ActionLog` constructor.

## Solution
### Implemented Fixes
*   Fixed `ActionExecutor._create_intercepted_log` to use the enriched `log_params` (which includes the action description) instead of the original `action.params` when creating an `ActionLog`.

### Prevention
*   Added `tests/unit/core/services/test_action_executor_regression.py` to verify that `handle_skipped_action` correctly preserves the action description in the resulting log's parameters. This ensures that even if an action is aborted, its original intent is correctly displayed in the final report.
