# Bug: Git Detection Tests Fail on Windows Due to Platform-Specific Path Check

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

Three unit tests for `_check_git_initialized` fail on Windows CI:

1. `test_check_git_not_detected_in_parent_repo_subfolder` – Expected "Git repository initialized", got "✓ Git repository detected".
2. `test_check_git_initialized_success` – Expected "Git repository initialized", got "✓ Git repository detected".
3. `test_check_git_initialized_failure` – Expected 0 secho calls, got 1.

All three failures share the same symptom: the function prints "✓ Git repository detected" when it should not. This indicates that on Windows, `(Path.cwd() / ".git").exists()` returns `True` even when the test tries to mock it to return `False`.

## Context & Scope

### Regressing Delta
The regression was introduced in the test files as part of Bug #07 (`07-git-detection-subfolder.md`), which added CWD-only git detection and corresponding tests. The test helper function `controlled_exists` in both `test_git_detection_cwd_only.py` and `test_session_cli_handlers.py` uses `str(self).endswith("/.git")` to check for `.git` paths. This is Unix-specific because `Path.__str__` uses backslashes on Windows. The production code (`_check_git_initialized` in `session_cli_handlers.py`) is not affected as it uses `pathlib` methods directly.

### Environmental Triggers
- OS: Windows (any version)
- The test's monkeypatch of `Path.exists` must intercept `.git` paths to control behavior.
- The `controlled_exists` function falls back to `return True` when the `endswith` condition is false.

### Ruled Out
- Production code in `session_cli_handlers.py` `_check_git_initialized` is correct; `(Path.cwd() / ".git").exists()` works identically on all platforms.
- The test's `monkeypatch.setattr("pathlib.Path.exists", controlled_exists)` itself is correct; the bug is in the `controlled_exists` logic.

## Diagnostic Analysis

### Causal Model
The three failing tests monkeypatch `Path.exists` with a `controlled_exists` function that intends to return `False` for paths ending with `/.git`. However, on Windows, `str(Path(...))` uses backslashes (e.g., `C:\Users\test\.git`), so the check `str(self).endswith("/.git")` never matches. Consequently, `controlled_exists` falls through to `return True` for `.git` paths, causing `_check_git_initialized` to believe a git repo exists and print "✓ Git repository detected".

### Discrepancies
- `controlled_exists` uses `endswith("/.git")` which is Unix-only. (Resolved: after confirmation and fix)

### Investigation History
1. Hypothesis: `controlled_exists` fails on Windows due to backslash vs forward slash. Observation: `Path.__str__` on Windows uses backslashes. Conclusion: pending verification via local probe.

## Solution

### Root Cause
The test helper function `controlled_exists` in both `test_git_detection_cwd_only.py` and `test_session_cli_handlers.py` used `str(self).endswith("/.git")` to detect `.git` paths during `Path.exists` monkeypatching. On Windows, `Path.__str__` uses backslashes (e.g., `C:\Users\runner\...\.git`), so the forward-slash `endswith` check never matches, causing the function to incorrectly return `True` (path exists) for `.git` paths. This made `_check_git_initialized` believe a git repository existed and print "✓ Git repository detected" instead of the expected fallback messages.

### Fix
Replaced the platform-dependent string check with `pathlib`'s platform-independent `.name` property, which extracts the final path component regardless of separator:
- `str(self).endswith("/.git")` → `self.name == ".git"`

Applied to three occurrences across two files:
1. `tests/suites/unit/adapters/inbound/test_git_detection_cwd_only.py` (line 14)
2. `tests/suites/unit/adapters/inbound/test_session_cli_handlers.py` (lines 113 and 178)

### Preventative Measures
1. **Regression Test Added**: `test_git_detection_path_helper.py` directly validates both the original (buggy) and fixed (correct) logic against `PurePosixPath` and `PureWindowsPath` to prevent regression.
2. **Pattern Documentation**: The regression test serves as documentation of the correct cross-platform path detection pattern for future test monkeypatches.
3. **Systemic Audit**: This class of bug (platform-dependent string checks on paths) is now documented in the Technical Debt section. Similar patterns in the codebase should use `pathlib`'s `.name`, `.parent`, `.suffix`, `.stem` properties instead of string manipulation.
