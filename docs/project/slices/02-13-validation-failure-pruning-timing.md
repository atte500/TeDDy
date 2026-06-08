# Slice: 02-13-Validation Failure Pruning Timing
- **Status:** Planned
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
- [ ] **Harness** - Update `test_prune_targets_anchored_validation_failure` if needed (existing test uses SUCCESS status, so it's already compatible). Add new tests for:
  - Validation failure without non-VF report is preserved.
  - Validation failure with non-VF report is pruned.
  - Non-VF report before VF turn does not trigger pruning.
- [ ] **Logic** - Modify `_apply_pruning_heuristics` in `session_pruning_service.py` to: (1) Accept a set of `non_vf_reports` (turn IDs with non-VF reports on disk). (2) Compute `is_currently_non_vf = current_status is not None and "Validation Failed" not in current_status`. (3) For each validation failure turn, prune it only if there exists a non-VF report (on disk or current) with a turn ID greater than the VF turn's ID.
- [ ] **Wiring** - Add an integration test in `test_session_pruning_persistence.py` or a new test file to verify end-to-end behavioral change.
- [ ] **Cleanup** - Remove `spikes/validate_heuristic_4_behavior.py` if exists.

## Implementation Notes
*(To be filled by Developer as implementation proceeds)*

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
