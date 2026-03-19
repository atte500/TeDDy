# Duplicate Validation Errors for READ Action

- **Status:** Resolved
- **MRE:** N/A (Internal unit test regression: `test_validate_rejects_read_if_file_already_in_context`)

## 1. Summary
The `PlanValidator` was returning two identical validation errors for a single `READ` action when the targeted file was both already in the project context and missing from the physical disk. This caused assertions in CI (expecting exactly 1 error) to fail with `AssertionError: assert 2 == 1`.

## 2. Investigation Summary
- **Hypothesis 1 (Validated):** The `ReadActionValidator.validate` method lacked an early return after identifying that a file was already in context.
- **Verification Spike:** Created an isolated test script `spikes/debug/test_read_validator_double_error.py` that simulated a file being both in-context and missing.
- **Results:** The spike confirmed that without an early return, the validator would append "is already in context" and then proceed to append "does not exist", resulting in two errors for the same action.

## 3. Root Cause
### Technical Cause
1. **Additive Logic:** The control flow in `src/teddy_executor/core/services/validation_rules/read.py` was additive. It checked for context presence and then *always* proceeded to check for file existence.
2. **Redundant Registration:** `PlanValidator` had hardcoded default validators in its `__init__` that were redundant with the container-injected validators. This duplication of registration (while not the direct cause of the dual-error report for a *single* validator) created a confusing and fragile configuration state.

### Systemic Cause
1. **Terminal Validation Assumption:** The logic failed to treat "already in context" as a terminal error for the `READ` action, allowing subsequent, redundant checks to execute.
2. **Configuration Fragmentation:** Maintaining default constructors inside services while using a DI container violates the single-source-of-truth principle for project wiring.

## 4. Verified Solution
1. **Early Return:** Modified `ReadActionValidator.validate` to return the error list immediately if the "already in context" check fails.
2. **Configuration Cleanliness:** Refactored `PlanValidator.__init__` to remove all hardcoded default validators, centralizing all registration in `src/teddy_executor/container.py`.

```python
# src/teddy_executor/core/services/validation_rules/read.py

if is_in_context:
    # ... report error
    return errors  # Fix: Stop validation for this action here
```

## 5. Preventative Measures
- **Regression Test:** The existing unit test `test_validate_rejects_read_if_file_already_in_context` in `tests/suites/unit/core/services/test_context_aware_validation.py` now serves as the permanent regression guard.
- **Code Review Standard:** Ensure that action validators follow a "fail-fast" pattern where the first terminal validation error stops further checks for that specific action to avoid redundant or confusing error reports.

## 6. Implementation Notes
The fix has been verified against the original failure condition using an isolation spike and checked against the full suite of unit and integration tests.
