# Bug: Auto-EDIT addition skipped on validation failure
- **Status:** Unresolved
- **Milestone:** [Milestone 2: Stability & Infrastructure](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** N/A
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)

## Symptoms
When an `EDIT` action fails validation (e.g., due to a mismatching FIND block), the file path of the EDIT target should still be auto-added to the turn context (since the file exists). Currently, the auto-addition is skipped entirely when validation fails. This means the working context is missing legitimate file references that were the target of a valid (but unmatchable) edit.

## Context & Scope
### Regressing Delta
TBD - This is a logical bug in the integration between the validation/execution pipeline and the context management system. The auto-addition of CREATE/EDIT paths to `turn.context` should occur independently of whether the action validates or executes successfully.

### Environmental Triggers
- Session mode (stateful execution) where `turn.context` is managed.
- An `EDIT` action whose FIND block fails to match (validation failure).

### Ruled Out
N/A

## Diagnostic Analysis
### Causal Model
The auto-addition of CREATE/EDIT file paths to `turn.context` happens in `SessionService._apply_execution_effects()`. This method iterates exclusively over `report.action_logs` to extract file paths. For validation failure scenarios (when an EDIT action's FIND block fails to match), the failure report is built by `SessionReplanner.build_failure_report()` with `action_logs=[]` (empty list). This means `_apply_execution_effects()` processes nothing and no paths are added.

However, the validation failure report DOES contain the original plan's actions via the `original_actions` field, which is populated from `plan.actions`. The `original_actions` field is completely ignored by `_apply_execution_effects()`. The fix is to also process `report.original_actions` as a fallback source when `action_logs` is empty (validation failure scenario).

### Discrepancies
- `_apply_execution_effects` only processes `action_logs`, but validation failure reports have empty `action_logs`. The `original_actions` field is populated but ignored. (Resolved: Confirmed via MRE that paths from `original_actions` are NOT added when `action_logs` is empty. Fixed by also processing `original_actions` as a fallback.)

### Investigation History
1. **Trace auto-addition code.** Found that `SessionService._apply_execution_effects()` handles context auto-addition by iterating over `report.action_logs`. Conclusion: This is where paths get added.
2. **Trace validation failure path.** Found that `SessionReplanner.build_failure_report()` creates reports with `action_logs=[]` but populates `original_actions` from `plan.actions`. Conclusion: The `original_actions` field contains the CREATE/EDIT actions that should have their paths auto-added, but is never consulted.
3. **Create MRE to reproduce bug.** MRE at `spikes/debug/16-probe-apply-execution-effects.py` confirmed: paths from `original_actions` NOT added when `action_logs` is empty. Simulated fix (processing `original_actions`) correctly adds paths. Conclusion: Bug confirmed and fix approach validated.

## Solution
### Root Cause
The auto-addition of CREATE/EDIT file paths to `turn.context` is handled by `SessionService._apply_execution_effects()`. This method exclusively iterates over `report.action_logs`. For validation failure scenarios (e.g., an EDIT action's FIND block fails to match), the failure report is built by `SessionReplanner.build_failure_report()` with `action_logs=[]`. Consequently, `_apply_execution_effects()` processes nothing and no file paths are added to the next turn's context.

The report does, however, contain the original plan's actions via the `original_actions` field (populated from `plan.actions` in `SessionOrchestrator._handle_logical_validation_errors()`). This field was never consulted.

### Fix
Modified `_apply_execution_effects()` in `SessionService` to also process `report.original_actions` when `report.action_logs` is empty (validation failure scenario). For each CREATE or EDIT action in `original_actions`, its `file_path` parameter is extracted, validated, and added to the context set.

### Preventative Measures
- **Defensive Pattern:** When processing a data source that may be empty in certain code paths, always check for a secondary fallback source that contains equivalent data.
- **Code Review Rule:** Any method that iterates over `action_logs` should be reviewed for the validation failure edge case where `action_logs` may be empty but `original_actions` is populated.
- **Test Coverage:** A unit test has been added that explicitly covers the validation failure path with empty `action_logs` and populated `original_actions`.
