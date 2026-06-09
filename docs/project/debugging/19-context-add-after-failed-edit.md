# Bug: File Not Added to turn.context After Failed EDIT
- **Status:** Resolved
- **Milestone:** [02-stability-and-polish](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** [N/A]
- **Specs:** [Stability & Bug Fixes](/docs/project/specs/stability-and-bugfixes.md)

## Symptoms
When an EDIT action fails (e.g., FIND block does not match), the target file path is NOT added to the next turn's `turn.context`. Expected behavior per the Turn Transition Algorithm: "For each READ, CREATE, and EDIT action, add its resource/file path to T_next/turn.context (provided the file exists)." The spec does not condition this on action success, so even failed EDIT actions should add the file to context.

## Context & Scope
### Regressing Delta
The auto-add to context feature was implemented as part of Slice 02-04 (Context Automation). The condition that filters by action success is the likely regression.

### Environmental Triggers
Any failed EDIT action will fail to add its file to turn.context.

### Ruled Out
- Not related to session execution logic.
- Not related to the model display bug previously investigated.

## Diagnostic Analysis
### Causal Model
The auto-addition of file paths to `turn.context` is implemented in `SessionService._apply_execution_effects()`. This method iterates over `report.action_logs` and *only* adds paths for actions with `ActionStatus.SUCCESS`. This violates the spec which requires adding paths regardless of action success, provided the file exists.

Two distinct failure modes exist:
1. **Validation Failure:** The plan fails pre-flight validation, producing a report with empty `action_logs` but populated `original_actions`. Bug 16 discovered this gap and added a fallback (`_apply_original_actions_effects`) to process `original_actions` when `action_logs` is empty.
2. **Execution Failure:** An action runs but fails (e.g., FIND block mismatch at runtime), producing a report with `action_logs` containing a FAILURE entry. The `_apply_execution_effects` method skips FAILURE entries, so the file path is silently dropped. No fallback exists for this scenario.

### Discrepancies
1. Validation failure reports have empty `action_logs`. The `_apply_execution_effects` adds nothing, while `original_actions` is populated. (Resolved: Bug 16 fix added `_apply_original_actions_effects` fallback.)
2. Execution failure reports have `action_logs` with FAILURE status. The `_apply_execution_effects` skips non-SUCCESS entries, so no path is added. (Unresolved: The spec requires adding paths regardless of success.)

### Investigation History
1. **Trace auto-add to context code.** Found `SessionService._apply_execution_effects()` iterates over `action_logs` and only adds for SUCCESS status. Conclusion: This is the central auto-addition method.
2. **Review Bug 16 findings.** Bug 16 identified validation failure gap (empty `action_logs` with populated `original_actions`). Fix applied: `_apply_original_actions_effects` fallback. Conclusion: Bug 16 resolved validation failure path.
3. **Identify execution failure gap.** Re-analysis of `_apply_execution_effects` reveals FAILURE status actions are skipped. The spec does not condition addition on success. Conclusion: Execution failures (runtime EDIT failures) are a likely remaining source of the user-reported bug.
4. **Create MRE to test both scenarios.** MRE at `spikes/debug/19-probe-apply-execution-effects.py` will run probe and confirm. (Awaiting probe results.)

## Solution
### Root Cause
`SessionService._apply_execution_effects()` in `session_service.py` filtered `action_logs` entries with `if log.status != ActionStatus.SUCCESS: continue`. This meant that `FAILURE` status entries (from runtime execution failures like mismatched FIND blocks) were silently skipped, and their file paths were never added to the next turn's `turn.context`. The spec requires that paths be added regardless of success, provided the file exists.

### Implementation
Changed the filter from `if log.status != ActionStatus.SUCCESS:` to a compound check: skip SKIPPED/PENDING, then for non-SUCCESS status only EDIT actions contribute their paths. This ensures that EDIT execution failures (e.g., mismatched FIND blocks) add their target file path to the next turn's context. READ and CREATE failures do NOT add paths, as per requirements. The `_apply_original_actions_effects` fallback (from Bug 16) handles validation failures (empty `action_logs` with populated `original_actions`).

### Regression Test
Added `tests/suites/unit/core/services/test_bug_19_execution_failure_context.py` with five test cases:
- Edit execution failure → path added
- Create execution failure → path NOT added (per user requirement)
- Skipped actions → path NOT added
- Pending actions → path NOT added
- Success actions → path added (baseline)

### Preventative Measures
- When filtering collections of execution outcomes, use inclusion lists (what to skip) rather than exclusion lists (what to process). This prevents future status values from being accidentally excluded.
- Add unit tests that explicitly test each `ActionStatus` value to ensure the filter behaves correctly for all statuses.
