# Slice: 02-13-Validation Failure Pruning Timing
- **Status:** To De-risk
- **Type:** Feature
- **Milestone:** [02-stability-and-polish](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [stability-and-bugfixes](/docs/project/specs/stability-and-bugfixes.md#4-validation-failure-pruning-timing)
- **Component Docs:** [session_pruning_service](/docs/architecture/core/services/session_pruning_service.md)

## Business Goal
Ensure that validation-failed turns are only pruned when a subsequent valid (green) plan exists, preserving the audit trail during chains of consecutive validation failures.

## Scenarios

> As a user, I want validation-failed turns to be pruned only when a subsequent green plan exists, so that I can diagnose the root cause of a chain of consecutive validation failures.

```gherkin
Feature: Validation Failure Pruning Timing
  Scenario: Validation failure without green anchor is preserved
    Given the session has a turn with a "Validation Failed" report
    And no subsequent green plan exists (no plan.md with green status)
    And no current turn has green status
    When the pruning service prunes the context
    Then the validation failure turn should remain selected (not pruned)

  Scenario: Validation failure with subsequent green plan is pruned
    Given the session has a turn with a "Validation Failed" report
    And a later turn exists with a green plan.md
    When the pruning service prunes the context
    Then the validation failure turn should be pruned

  Scenario: Validation failure with current green status is pruned
    Given the session has a turn with a "Validation Failed" report
    And the current turn status is green
    When the pruning service prunes the context
    Then the validation failure turn should be pruned

  Scenario: Chain of validation failures without green anchor are all preserved
    Given the session has multiple consecutive turns with "Validation Failed" reports
    And no subsequent green plan exists
    When the pruning service prunes the context
    Then all validation failure turns should remain selected
```

## Edge Cases
- **Empty turn_statuses**: If no plan.md exists on disk, `is_latest_green` cannot be computed. Heuristic 4 should still run if `is_currently_green` is True (current turn green), because this indicates a healthy state. If both are absent, validation failures are preserved.
- **Config disabled**: If `auto_pruning.prune_validation_failures` is False, Heuristic 4 is skipped entirely regardless of green-state guard.
- **Mixed failure types**: A turn with both validation failure and non-green plan should be handled by whichever heuristic runs first. Since Heuristic 4 now runs inside the guard, both Heuristics 3 and 4 share the same condition. A validation failure turn with a non-green plan will be pruned with whichever reason is set first (Validation Failure takes priority over Recovery Cleanup due to `setdefault`).
- **Empty validation_failures set**: If no validation failures are detected, Heuristic 4 is a no-op.

## Deliverables
- [ ] **Harness** - Update `test_prune_targets_anchored_validation_failure` to pass a green anchor (e.g., `current_status="SUCCESS 🟢"`) so the test remains valid. Add new tests for:
  - Validation failure without green anchor is preserved.
  - Validation failure with green anchor is pruned.
- [ ] **Logic** - Modify `_apply_pruning_heuristics` in `session_pruning_service.py` to move the Heuristic 4 loop inside the `if is_currently_green or is_latest_green:` guard.
- [ ] **Wiring** - Add an integration test in `test_session_pruning_persistence.py` or a new test file to verify end-to-end behavioral change.
- [ ] **Cleanup** - Remove `spikes/validate_heuristic_4_behavior.py`.

## Implementation Notes
*(To be filled by Developer as implementation proceeds)*

## Implementation Plan
### Code Change
In `session_pruning_service.py`, `_apply_pruning_heuristics`:

```python
# Current (unconditional):
# Heuristic 4: Validation Failure
for tid in validation_failures:
    turns_to_prune[str(tid)] = "Plan failed validation"

# Heuristic 3: Recovery Cleanup
is_currently_green = current_status is not None and "🟢" in current_status
if prune_non_green and turn_statuses:
    latest_on_disk = max(turn_statuses.keys())
    is_latest_green = turn_statuses[latest_on_disk]
    if is_currently_green or is_latest_green:
        for tid, is_green in turn_statuses.items():
            if not is_green:
                turns_to_prune.setdefault(...)
```

```python
# New (guarded):
is_currently_green = current_status is not None and "🟢" in current_status
if prune_non_green and turn_statuses:
    latest_on_disk = max(turn_statuses.keys())
    is_latest_green = turn_statuses[latest_on_disk]
else:
    is_latest_green = False

if is_currently_green or is_latest_green:
    # Heuristic 4: Validation Failure (MOVED INSIDE GUARD)
    for tid in validation_failures:
        turns_to_prune[str(tid)] = "Plan failed validation"
    # Heuristic 3: Recovery Cleanup
    if prune_non_green and turn_statuses:
        for tid, is_green in turn_statuses.items():
            if not is_green:
                turns_to_prune.setdefault(...)
```

### Test Strategy
- Use `TestHarnessTriad`:
  - **Driver**: `PlanBuilder` to construct context items with specific path/report content.
  - **Observer**: `FileSystemObserver` not needed for unit tests; directly assert on `context.items`.
  - **Setup**: `MockConfigService` and `MockFileSystemManager` with controlled file content.
- Existing test `test_prune_targets_anchored_validation_failure` must be updated because it currently passes `current_status=None` and expects unconditional pruning. It will be modified to pass `current_status="SUCCESS 🟢"` to demonstrate the new anchored behavior.
- New test `test_validation_failure_without_green_anchor_is_preserved` verifies the conditional behavior.

### Integration Test
Add a test in `test_session_pruning_persistence.py` or a new file `test_validation_failure_pruning_timing_integration.py` that:
1. Creates a session with validation failure turns.
2. Runs pruning without green status.
3. Asserts validation failures are preserved.
4. Runs pruning with green status.
5. Asserts validation failures are pruned.
