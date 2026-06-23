# Bug: POSIX Absolute CWD Validation Fails on Windows

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

`test_validate_execute_fails_with_posix_absolute_cwd` fails on Windows CI. The test expects 1 validation error when an EXECUTE action has CWD set to a POSIX absolute path (`/etc`), but 0 errors are returned. This means the validator does not reject POSIX absolute paths on Windows.

## Context & Scope

### Regressing Delta
Unknown yet. This test existed before the previous bug fix (which only touched test files for git detection). The pre-existing test was never run on Windows CI before, or was passing due to different conditions. The CI run after merging the git detection fix is the first time this test ran.

### Environmental Triggers
- OS: Windows (any version)
- The validation rule for EXECUTE cwd must check for absolute paths using a platform-dependent method.

### Ruled Out
- The previous git detection fix is unrelated.

## Diagnostic Analysis

### Causal Model
The `validate_path_is_safe` function in `helpers.py` uses `os.path.isabs(path_str)` to detect absolute paths. On Windows, `os.path.isabs` delegates to `ntpath.isabs`, which considers paths starting with `/` as **relative** unless they include a drive letter (e.g., `C:\`) or a backslash prefix. Therefore, on Windows, a POSIX-style absolute path like `/etc` is not recognized as absolute, causing the validator to accept it without error.

The fix must replace the platform-dependent `os.path.isabs` with a cross-platform check that detects any path starting with `/` as absolute, regardless of OS.

### Discrepancies
(To be populated.)

### Investigation History
1. Hypothesis: The absolute path check in `_get_validated_path` uses a platform-dependent method (e.g., `Path.is_absolute()`, `startswith("/")`) that fails on Windows. Observation: `validate_path_is_safe` uses `os.path.isabs(path_str)`, which on Windows (ntpath) returns False for paths starting with `/` without a drive letter. Conclusion: Confirmed – `os.path.isabs` is platform-dependent and fails to detect POSIX absolute paths on Windows.

## Solution

### Root Cause
The `validate_path_is_safe` function in `helpers.py` used `os.path.isabs(path_str)` to detect absolute paths. On Windows, `os.path.isabs` delegates to `ntpath.isabs`, which considers POSIX-style absolute paths (starting with `/`) as **relative** unless they include a drive letter (e.g., `C:\`) or a backslash prefix. Therefore, on Windows, an EXECUTE action with `cwd: "/etc"` was incorrectly accepted without validation error.

### Fix
Replaced the single `os.path.isabs(path_str)` check with a combined cross-platform check:
- `os.path.isabs(path_str)` → `path_str.startswith("/") or os.path.isabs(path_str)`

This ensures that POSIX absolute paths (starting with `/`) are detected as absolute on all platforms, including Windows.

### Files Changed
| File | Change |
|------|--------|
| `src/teddy_executor/core/services/validation_rules/helpers.py` | Added `path_str.startswith("/") or` before `os.path.isabs` in `validate_path_is_safe` |
| `tests/suites/unit/core/services/test_validation_path_detection.py` | **New** regression test for cross-platform absolute path detection |

### Preventative Measures
1. **Regression Test Added**: `test_validation_path_detection.py` validates both original and fixed logic across platforms using `PurePosixPath` and `PureWindowsPath` concepts.
2. **Pattern Documentation**: The regression test serves as documentation of the correct cross-platform absolute path detection pattern.
3. **Systemic Audit**: This is the same class of bug as #12 (platform-dependent path detection). Both bugs used platform-specific functions (`str.endswith("/.git")`, `os.path.isabs`) instead of cross-platform alternatives (`Path.name`, `str.startswith("/")`). Future code should prefer `pathlib` properties and explicit cross-platform checks when detecting path characteristics.
