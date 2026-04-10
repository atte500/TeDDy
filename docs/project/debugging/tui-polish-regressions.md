# Bug: TUI Crash and Polish Regressions

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** [10-09-tui-polish-performance](../../slices/10-09-tui-polish-performance.md)
- **Specs:** [interactive-session-workflow](../../specs/interactive-session-workflow.md)

## Symptoms
1. **Crash:** Selecting items in the Rationale list in the right panel causes a crash: `AttributeError: 'dict' object has no attribute 'executed'`.
2. **UX Regression (Action Log):** `CREATE`/`EDIT` actions show too much detail in logs; 'e' (edit) remains available after execution when 'd' (details) should replace it.
3. **UX Regression (READ):** `READ` action triggers an unnecessary "Finished viewing?" popup.
4. **Acceptance/Unit Regressions:** 14 tests failing, including dual-pane layout verification and action modification tracking.

## System Model

### Understanding
The TUI (`ReviewerApp`) uses a hierarchical tree structure with virtual roots for Rationale and Action Plan sections.

**Root Causes Resolved:**
1. **Crash:** Added `isinstance(action, ActionData)` check in `on_list_view_selected_logic` to handle non-action nodes (Rationale).
2. **Navigation:** Updated `TuiDriver` and tests to account for the deeper tree hierarchy (6+ "downs" to reach the first action).
3. **Structure:** Aligned tests to query for `Static` instead of `Label` in `DetailItem` for performance-optimized log previews.
4. **Logic:** Adjusted `resolve_action_parameters` and tests to handle stringified list parameters and filtered descriptions.

### Discrepancies
- None.

## Solution

### Implemented Fixes
- **Logic:** Fixed crash in `on_list_view_selected_logic` via type-checking.
- **Logic:** Updated `check_action_logic` to correctly toggle bindings based on `executed` state.
- **TUI:** Optimized `READ` action to use `suspend()` instead of unnecessary popups.
- **Harness:** Updated `TuiDriver` and acceptance tests to match the new tree navigation and interaction sequence (removing redundant 'y' keys).

### Prevention
- **Regression Tests:** Standardized the `TUI interaction sequence` across all acceptance tests.
- **Poka-Yoke:** Added defensive type checks in all TUI logic handlers that traverse the `ActionTree`.
