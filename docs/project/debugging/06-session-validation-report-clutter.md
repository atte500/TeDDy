# Bug: Redundant Resource Contents in Session Validation Reports

- **Status:** Unresolved
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** [docs/project/slices/02-06-orchestrator-hardening.md](/docs/project/slices/02-06-orchestrator-hardening.md)
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)

## Symptoms
In session mode, when a plan fails validation (e.g., an `EDIT` mismatch), the resulting report incorrectly includes a "Resource Contents" section containing the full file content.

**Expected Behavior:** The "Resource Contents" section should be suppressed in session mode (as the content is already in `input.md`), but the "Closest Match Diff" (which is part of the error message string) should be preserved.

## Context & Scope
### Regressing Delta
The `is_session` flag is correctly detected in `SessionOrchestrator.execute` but is not passed to:
1.  `SessionReplanner.build_failure_report`
2.  `SessionLifecycleManager.trigger_replan`

Additionally, `SessionReplanner.gather_failed_resources` gathers full file content even when in session mode, leading to unnecessary I/O.

### Ruled Out
- **Template Logic:** `execution_report.md.j2` has been verified via spike to correctly suppress the section if `is_session` is `True`.

## Diagnostic Analysis
### Causal Model
1.  `SessionOrchestrator` detects `is_session=True`.
2.  `PlanValidator` returns logical errors.
3.  `SessionOrchestrator` calls `_handle_logical_validation_errors`, which calls `trigger_replan` or `build_failure_report`.
4.  These calls do not currently accept or propagate the `is_session` flag.
5.  The resulting `ExecutionReport` has `is_session=False` (default), causing the template to render full file snapshots.

### Investigation History
1. **Hypothesis:** `is_session` flag is lost. **Observation:** Grep and code review confirm the flag is not passed to the replanner or lifecycle manager. **Conclusion:** Valid.
2. **Hypothesis:** Template logic is broken. **Observation:** Spike in `spikes/verify_session_report_flag.py` confirms template works if flag is set. **Conclusion:** Ruled out.

## Solution
1.  **Contract Update**: Update `SessionReplanner.build_failure_report` and `SessionLifecycleManager.trigger_replan` to accept an `is_session: bool` parameter.
2.  **Propagate Flag**: Ensure `SessionOrchestrator` passes the detected `is_session` flag to these methods.
3.  **Optimize I/O**: Update `SessionReplanner.gather_failed_resources` to skip I/O if `is_session` is `True`.
