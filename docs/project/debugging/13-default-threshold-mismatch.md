# Bug: Default Similarity Threshold Test Mismatch After Config Change
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
- **Expected:** The acceptance test `test_fallback_to_default_threshold` passes, asserting that the execution report contains `Similarity Threshold:** 1.00` when no config specifies the threshold.
- **Actual:** The test fails because the report now contains `Similarity Threshold:** 0.95` due to a recently changed default from 1.00 to 0.95.
- **Reproduction Steps:** Run `poetry run pytest tests/suites/acceptance/test_similarity_threshold_config.py -k test_fallback_to_default_threshold --no-header -q` (fails with `AssertionError`).

## Context & Scope
### Regressing Delta
The default similarity threshold was changed from `1.0` to `0.95` via two commits:
1. **Commit `30e08e2f` (2026-06-04):** Changed `DEFAULT_SIMILARITY_THRESHOLD` in `src/teddy_executor/core/domain/models/plan.py` from `1.0` to `0.95`.
2. **Commit `255fd364` (2026-06-04):** Updated `src/teddy_executor/resources/config/config.yaml` to set `similarity_threshold: 0.95`.

### Environmental Triggers
None – the test diverges from the new default regardless of environment.

### Ruled Out
- No other tests or active documentation contain stale references to the old default.
- Tests that explicitly set a threshold of `1.0` in their config (e.g., `test_resilient_edit_matching_integration.py`) are unaffected.
- Documentation (architecture specs) already references the new default of `0.95`.

## Diagnostic Analysis
### Causal Model
The acceptance test `test_fallback_to_default_threshold` simulates running TeDDy without a `.teddy/config.yaml`. It exercises the fallback path in `resolve_similarity_threshold()` (`helpers.py`), which reads from `DEFAULT_SIMILARITY_THRESHOLD = 0.95`. The test's assertion `assert "Similarity Threshold:** 1.00"` was not updated when the default was lowered from `1.0` to `0.95`, causing a mismatch. The test's docstring also contained an even older stale value (`0.97`).

### Discrepancies
1. Test expects `1.00` but default is now `0.95`. (resolved: the test's assertion, comment, and docstring were updated to reflect the correct default of `0.95`.)

### Investigation History
1. Initial symptom identified: `test_fallback_to_default_threshold` fails with `AssertionError` expecting `1.00` but observing `0.95`.
2. `git log` and `git blame` confirmed the two regressing deltas (commits `30e08e2f` and `255fd364`).
3. `git grep` confirmed no other tests or docs have stale references to the old default.
4. Fix: Updated the test's docstring (line 48), comment (line 69), and assertion (line 73) from `1.00`/`0.97` to `0.95`.

## Solution
### Root Cause
The default similarity threshold was changed from `1.0` to `0.95` in both the code constant and the default config file, but the acceptance test that verifies the fallback behavior was not updated.

### Fix Applied
Updated three lines in `tests/suites/acceptance/test_similarity_threshold_config.py`:
- Line 48 docstring: `0.97` → `0.95`
- Line 69 comment: `1.00` → `0.95`
- Line 73 assertion: `1.00` → `0.95`

### Preventative Measures
To prevent this class of issue across the codebase:
1. **Config-Driven Testing:** When changing defaults in `config.yaml` or code constants, automatically run a grep for ALL hardcoded references to the old value in test assertions and documentation to ensure synchronization.
2. **Test for Default Parity:** Consider adding a dedicated unit test that asserts `DEFAULT_SIMILARITY_THRESHOLD == <expected>` to act as a sentinel for unintended changes. Currently, the acceptance test implicitly verifies the fallback, but a direct unit test would catch mismatches earlier.
9. **Pre-commit Hook:** A pre-commit script could verify that any change to `plan.py`'s default constant or `config.yaml`'s similarity threshold triggers a scan of test files for stale assertions.
