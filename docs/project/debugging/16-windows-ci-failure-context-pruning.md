# Bug: Windows CI Failure in Context Pruning
- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** [00-04-context-management-ui](../slices/00-04-context-management-ui.md)

## Symptoms
### Expected Behavior
CI should pass on all platforms including Windows.

### Actual Behavior
Windows CI job is failing after recent context management and pruning implementation.

## Context & Scope
### Regressing Delta
Recent changes to `ContextService` and `SessionOrchestrator` regarding context gathering and pruning. Specifically, the implementation of `_apply_auto_pruning` and git status parsing.

### Environmental Triggers
- OS: Windows (CI)
- Logic: Context Management / Pruning heuristics.

### Ruled Out
- [TBD]

## Diagnostic Analysis
### Causal Model
The `SessionOrchestrator` gathers project context via `ContextService` before calling the `IPlanReviewer`. During `_prepare_plan`, it validates the plan actions (like `EDIT` or `PRUNE`) against the gathered `context_paths`.

The `is_path_in_context` helper (used by validation rules) performs direct string matching. On Windows, resolved context paths use backslashes (`\`), while TeDDy plans use forward slashes (`/`). This mismatch causes `is_path_in_context` to return `False`, triggering a validation failure.

When validation fails in session mode, `SessionOrchestrator` returns an `ExecutionReport` for a re-plan turn immediately, bypassing the `IPlanReviewer.review` call. This explains the 0-call count on Windows.

### Discrepancies
- `POSIXPathMock` appears in Windows logs. Conflict: Windows uses `WindowsPath`. (Resolved: `POSIXPathMock` is a custom test harness component in `tests/harness/setup/mocking.py` used to normalize mock calls to POSIX format. However, the SUT's interaction with the real filesystem on Windows yields backslashes which aren't caught by this mock normalization in `ContextService`).
- `reviewer.review` called 0 times. Conflict: The test explicitly triggers a resume which should invoke the reviewer in TUI mode. (Resolved: Validation failure in `SessionOrchestrator` causes an early exit to the re-plan loop).

### Investigation History
1. View CI logs for run 25722599012. Identified `Test Suite (windows-latest)` failure (ID 75527218693).
2. Fetch logs for job ID 75527218693. Observed `AssertionError` in `test_auto_pruning_heuristics_acceptance` (Review called 0 times) and presence of `POSIXPathMock`.
3. Analyze `ExecutionOrchestrator`, `TestEnvironment`, and `mocking.py` for path-related issues.
4. Read validation rules in `edit.py` and `filesystem.py` to check path normalization. Found that `is_path_in_context` is the shared bottleneck.
5. Read `helpers.py` and confirmed `is_path_in_context` lacks slash normalization.
6. Created MRE `spikes/debug/16-mre-path-context.py` and confirmed it fails with slash mismatch.
7. Verified fix in `spikes/debug/16-mre-path-context-verified.py` by adding `.replace("\\", "/")` to the normalization logic.
4. Read validation rules in `edit.py` and `filesystem.py` to check path normalization.
5. Read `helpers.py` to inspect `is_path_in_context` implementation.

## Solution
The root cause is a lack of internal slash normalization in path-matching helpers. The fix involves updating `is_path_in_context` in `src/teddy_executor/core/services/validation_rules/helpers.py` to replace all backslashes (`\`) with forward slashes (`/`) in both the target and context paths during comparison. Additionally, extraction logic in `SessionService` and `ContextService` should be hardened.

Verified fix in `spikes/debug/16-mre-path-context-verified.py`.
