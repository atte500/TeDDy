# Bug: Windows context path backslash mismatch in assertion

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

**Expected:** The acceptance test `test_start_command_accepts_context_and_overrides` (`tests/suites/acceptance/test_cli_context_flag.py`) passes on Windows.

**Actual:** The test fails on Windows because line 53 computes `normalized = str(extra_file).lstrip("/")`, producing a path with backslashes (e.g., `C:\Users\runneradmin\...\extra.py`), while `session.context` stores paths with forward slashes (e.g., `C:/Users/runneradmin/.../extra.py`) due to normalization in `session_service.py`. The assertion `assert normalized in session_context` therefore fails.

**Minimal Reproduction Steps:**
1. Run `pytest tests/suites/acceptance/test_cli_context_flag.py::test_start_command_accepts_context_and_overrides` on Windows (or simulate Windows path behavior).
2. Observe failure: `assert normalized in session_context` where `normalized` uses backslashes but `session_context` uses forward slashes.

## Context & Scope

### Regressing Delta
The regression was introduced in commit `f3186c86f2d6a9b8c3c70113605c38abb5cdab67` ("fix: apply casefold to agent name comparisons and normalize context paths"). This commit modified `tests/suites/acceptance/test_cli_context_flag.py` to add the assertion `normalized = str(extra_file).lstrip("/")` and the corresponding `assert normalized in session_context`. The normalizing code in `src/teddy_executor/core/services/session_service.py` (lines 134, 226-235) correctly converts backslashes to forward slashes before stripping, but the test assertion does not perform equivalent normalization.

### Environmental Triggers
- **OS:** Windows (windows-latest in CI)
- The failure does not occur on Linux or macOS because those platforms use forward slashes natively.

### Ruled Out
- The production normalization logic in `session_service.py` is correct; it properly converts backslashes to forward slashes.
- The issue is solely in the test assertion, which lacks backslash-to-forward-slash normalization before comparison.

## Diagnostic Analysis

### Causal Model
The `SessionService._normalize_resource_paths()` method (line 134) and `SessionService._normalize_path()` method (line 226) both convert backslashes to forward slashes using `.replace("\\", "/")` and then strip leading `./` prefixes and leading slashes. However, the test `test_start_command_accepts_context_and_overrides` computes a normalized path using Python's `pathlib.Path.lstrip("/")` which does NOT convert backslashes to forward slashes. On Windows, `str(extra_file)` returns a path with backslashes (e.g., `C:\Users\...\extra.py`), so `normalized` retains backslashes. The session.context file, written by `_normalize_resource_paths()`, uses forward slashes. Hence, the `assert normalized in session_context` fails on Windows.

### Discrepancies
- The test assertion normalizes paths differently than the production code on Windows.
- (Resolved: MRE empirically demonstrates that `lstrip("/")` alone does not convert backslashes to forward slashes, explaining the CI failure on Windows.)

### Investigation History
1. Hypothesis: The test failure on Windows is due to path separator mismatch. Observation: CI log shows `assert normalized in session_context` failing on windows-latest. Conclusion: The test uses `lstrip("/")` without converting backslashes, while production code uses `replace("\\", "/")` before stripping.
2. Hypothesis: A simulated Windows path in an MRE will demonstrate the exact mismatch. Observation: Running `spikes/debug/19-windows-context-path-backslash-mre.py` shows that `str(path).lstrip("/")` produces `C:\Users\runneradmin\...` (backslashes retained), while production normalization `path.strip().replace("\\", "/").lstrip("/")` produces `C:/Users/runneradmin/...` (forward slashes). Conclusion: The causal model is confirmed — the test assertion lacks backslash-to-forward-slash normalization that production code performs.

## Solution

### Root Cause
The acceptance test `test_start_command_accepts_context_and_overrides` in `test_cli_context_flag.py` used `str(extra_file).lstrip("/")` to normalize a path before comparing it with `session.context` content. On Windows, `str(Path)` returns backslashes (e.g., `C:\Users\...`), while the production code in `SessionService._prepare_session_context()` converts backslashes to forward slashes via `.replace("\\", "/")` before writing to `session.context`. The test assertion did not perform the same backslash-to-forward-slash conversion, causing the assertion to fail on Windows.

### Fix
Changed both occurrences of `str(extra_file).lstrip("/")` to `str(extra_file).replace("\\", "/").lstrip("/")` in `tests/suites/acceptance/test_cli_context_flag.py`. This matches the normalization already performed by the production code.

### Preventative Measures
- Added a regression test (`test_context_path_normalization.py`) that explicitly tests path normalization on a simulated Windows-style path, ensuring the test assertion normalization matches production normalization.
- General principle: Cross-platform path comparisons should always normalize separators (backslash to forward slash) before comparing, to prevent OS-dependent CI failures. Any test that reads a file path from the filesystem and compares it to a string should apply `.replace("\\", "/")` first.
