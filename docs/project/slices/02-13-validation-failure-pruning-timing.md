# Slice: 02-13-Validation Failure Pruning Timing
- **Status:** In Progress
- **Type:** Feature
- **Milestone:** [02-stability-and-polish](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [stability-and-bugfixes](/docs/project/specs/stability-and-bugfixes.md#4-validation-failure-pruning-timing)
- **Component Docs:** [session_pruning_service](/docs/architecture/core/services/session_pruning_service.md)
- **Prototype:** [spikes/prototypes/02-13-validation-failure-timing.py](/spikes/prototypes/02-13-validation-failure-timing.py)

## Business Goal
Ensure that validation-failed turns are only pruned when a subsequent report.md without "Validation Failed" status exists (a "non-VF report"), preserving the audit trail during chains of consecutive validation failures.

## Scenarios

> As a user, I want validation-failed turns to be pruned only when a subsequent report.md without "Validation Failed" status exists, so that I can diagnose the root cause of a chain of consecutive validation failures.

```gherkin
Feature: Validation Failure Pruning Timing (Report-Based Anchor)
  Scenario: Validation failure without non-VF report is preserved
    Given the session has a turn with a "Validation Failed" report
    And no later turn has a report.md with a status other than "Validation Failed"
    And the current turn status is "Validation Failed"
    When the pruning service prunes the context
    Then the validation failure turn should remain selected (not pruned)

  Scenario: Validation failure with subsequent non-VF report is pruned
    Given the session has a turn with a "Validation Failed" report
    And a later turn has a report.md with overall status "SUCCESS" (non-VF)
    When the pruning service prunes the context
    Then the validation failure turn should be pruned

  Scenario: Validation failure with current non-VF status is pruned
    Given the session has a turn with a "Validation Failed" report
    And the current turn's overall status is "SUCCESS" (not "Validation Failed")
    When the pruning service prunes the context
    Then the validation failure turn should be pruned

  Scenario: Chain of validation failures without non-VF report are all preserved
    Given the session has multiple consecutive turns with "Validation Failed" reports
    And no later turn has a non-VF report
    When the pruning service prunes the context
    Then all validation failure turns should remain selected
```

## Edge Cases
- **Empty turn_statuses**: If no plan.md exists on disk, Heuristic 4 still collects non-VF reports from report.md files. The non-VF report guard works independently of `turn_statuses`. If both no non-VF reports on disk and current_status is "Validation Failed", validation failures are preserved.
- **Config disabled**: If `auto_pruning.prune_validation_failures` is False, Heuristic 4 is skipped entirely regardless of guard.
- **Mixed failure types**: A turn with both validation failure and non-green plan: Heuristic 3 (Recovery Cleanup) still runs under its own guard (green plan check). Heuristic 4 now runs under the non-VF report guard. The two guards can produce different results. The order remains: Heuristic 4 runs first (if guard met), then Heuristic 3 appends via `setdefault`.
- **Empty validation_failures set**: If no validation failures are detected, Heuristic 4 is a no-op.
- **Non-VF report before VF turn**: If a non-VF report exists on turn 01 and VF on turn 02, the VF should NOT be pruned because the non-VF report is earlier. Only VF turns *before* the latest non-VF report are pruned.

## Deliverables
- [x] **Logic** - Modify `_apply_pruning_heuristics` in `session_pruning_service.py` to guard Heuristic 4 by the existence of a non-VF report (a later turn with a report.md whose overall status is not "Validation Failed"). Accept a set of `non_vf_reports` and compute `is_currently_non_vf`. For each validation failure turn, prune only if there exists a non-VF report (on disk or current turn) with a turn ID greater than the VF turn's ID. Also update `_collect_turn_metadata` to collect `non_vf_reports`. Add unit tests for the new behavior:
  - Validation failure without non-VF report is preserved.
  - Validation failure with non-VF report is pruned.
  - Non-VF report before VF turn does not trigger pruning.
- [ ] **Wiring** - Add an integration test in `test_session_pruning_persistence.py` or a new test file to verify end-to-end behavioral change.

## Implementation Notes

### Logic Deliverable (Completed 2026-06-08)

#### Changes to `session_pruning_service.py`:
1. **New helper `_check_report_is_non_vf_report`**: Checks if a report file exists and does NOT have "Validation Failed" overall status. Mirrors `_check_report_failed_validation` structure but inverts the check. Returns `False` if the file doesn't exist (can't read) to avoid treating missing files as non-VF anchors.
2. **`_update_turn_metadata_from_item`**: Added collection of `non_vf_reports` turn IDs when a report is detected as non-VF. Stored in the shared state dict alongside `validation_fails` and `messages`.
3. **`_collect_turn_metadata`**: Initialized `non_vf_reports` set in the return tuple (fourth element). Updated type signature to return `tuple[Dict[int, bool], set[int], set[int], set[int]]`.
4. **`_identify_turns_to_prune`**: Unpacked the new fourth return value and passed `non_vf_reports` to `_apply_pruning_heuristics`.
5. **`_apply_pruning_heuristics`**: Added `non_vf_reports` parameter (optional set). Implemented guard logic:
   - `is_currently_non_vf` = current_status exists and doesn't contain "Validation Failed"
   - `latest_non_vf_turn` = max of on-disk non-VF reports (or -1 if none)
   - For each validation failure turn: prune if `tid < latest_non_vf_turn` OR if `is_currently_non_vf` (current turn acts as an anchor after all on-disk turns)

#### New Unit Tests (in `test_session_pruning_status_anchoring.py`):
1. `test_validation_failure_without_non_vf_report_is_preserved`: Single VF turn, current_status="Validation Failed" → preserved (no anchor)
2. `test_validation_failure_with_non_vf_report_is_pruned`: VF turn 01 + non-VF turn 02 → VF pruned
3. `test_non_vf_report_before_vf_turn_does_not_trigger_pruning`: Non-VF turn 01 + VF turn 02 → both preserved (anchor before VF)

#### Prototype Validation
The prototype at `spikes/prototypes/02-13-validation-failure-timing.py` was used as a behavioral reference. Its logic for `is_currently_non_vf` guard was specifically adapted: the simplified version in production (`is_currently_non_vf = True` prunes ALL VF turns) was chosen over the prototype's more complex `tid < current_turn_id` logic because the current turn is always the latest turn overall, so any VF on disk must have occurred before it.

#### Regression Verification
Existing test `test_prune_targets_anchored_validation_failure` passes because:
- The report has "Overall Status: SUCCESS" (not a validation failure)
- Heuristic 4 only operates on `validation_failures` set
- The SUCCESS report is classified as a non-VF report (collected), but since it's the only turn, there are no VF turns to prune

## Implementation Plan
### Code Change
In `session_pruning_service.py`:

#### `_collect_turn_metadata` additions:
Add collection of `non_vf_reports` set: for each `report.md`, if `_check_report_failed_validation` is False (i.e., report exists but is NOT a validation failure), add the turn ID to `non_vf_reports`.

#### `_apply_pruning_heuristics` changes:
The function signature must remain unchanged for backward compatibility, but the guard logic changes:

```python
# Heuristic 4: Validation Failure (guarded by existence of non-VF report)
is_currently_non_vf = current_status is not None and "Validation Failed" not in current_status

# Find latest non-VF report on disk
latest_non_vf_turn = max(non_vf_reports) if non_vf_reports else -1

for tid in sorted(validation_failures):
    # Prune if there is a non-VF report after this VF turn
    if tid < latest_non_vf_turn or (tid < current_turn_id and is_currently_non_vf):
        turns_to_prune[str(tid)] = "Plan failed validation"
```

Note: `current_turn_id` is the turn ID of the current turn (if available from `turn_statuses` max). If not available, use a sentinel large number (e.g., 999) to ensure all VF turns before current get pruned.

Simpler: if `is_currently_non_vf`, treat it as an anchor after all on-disk turns. So prune all VF turns that are less than or equal to the latest on-disk non-VF report, PLUS all VF turns if current turn is non-VF (since it's after all on-disk turns).

### Test Strategy
- **Driver**: `PlanBuilder` to construct context items with specific path/report content.
- **Observer**: Directly assert on `context.items`.
- **Setup**: `MockConfigService` and `MockFileSystemManager` with controlled file content.
- Existing test `test_prune_targets_anchored_validation_failure` passes `current_status=None` and expects the report to NOT be pruned (since status is SUCCESS but no non-VF report anchor). This test already works correctly because the report is SUCCESS, not a validation failure.
- New test `test_validation_failure_without_non_vf_report_is_preserved` verifies the conditional behavior.

### Integration Test
Add a test in `test_session_pruning_persistence.py` or a new file `test_validation_failure_pruning_timing_integration.py` that:
1. Creates a session with validation failure turns.
2. Runs pruning with `current_status="Validation Failed"` (no non-VF anchor).
3. Asserts validation failures are preserved.
4. Runs pruning with `current_status="SUCCESS"` (non-VF current turn — status does not contain "Validation Failed").
5. Asserts validation failures are pruned.
