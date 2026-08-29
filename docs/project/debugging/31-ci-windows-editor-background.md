# Bug: CI Windows Editor Background Test Regression

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

- **Expected:** `test_no_editor_returns_empty_string_and_logs` should pass on all OS platforms (Windows, macOS, Linux).
- **Actual:** The test fails on Windows CI with an unhandled exception in `_launch_editor_background` when `find_editor()` returns `None`.
- **Reproduction Steps:** Trigger CI on branch `main` with Windows runner (e.g., `windows-latest`). The test suite fails at `tests/suites/unit/adapters/outbound/test_console_ask_loop_editor_background.py:380`.

## Context & Scope

### Regressing Delta
The recent PR #2657 (`refactor(tui-plan-reviewer-editor-fixes)`) modified the editor subsystem. The exact breakage is in `_launch_editor_background` which now creates a temp file via `self._system_env.create_temp_file()` **before** the `if not editor_cmd:` early-return check. This is likely the root cause: on Windows, `create_temp_file` (if not properly mocked or if the mock returns a non-string path) can cause an error before the early-return is reached.

### Environmental Triggers
- **OS:** Windows (fails on `windows-latest` CI, passes on macOS and Linux).
- **Runner:** CI workflow with `windows-latest` label.
- **Test fixture:** `mock_system_env` must provide a valid `create_temp_file` return (a string path). If not, the `with open(temp_path, "w", ...)` call will fail.

### Ruled Out
- Not related to `_flush_stdin` (patched at class level).
- Not related to `find_editor` return value (returns `None` as expected).
- Not related to TTY detection (patched to return `True`).

## Diagnostic Analysis

### Causal Model
`_launch_editor_background` unconditionally creates a temp file via `self._system_env.create_temp_file(suffix=".md")` **before** checking `if not editor_cmd: return ""`. This ordering means that even when no editor is configured, the code first creates a temp file using the mock's return value (`"/tmp/fake_editor.md"`).

On Unix-like systems (macOS, Linux), `/tmp` exists as a symlink to `/private/tmp`, so `open("/tmp/fake_editor.md", "w")` succeeds even though it's a mock path — it creates a real file at that location.

On Windows, `/tmp` does not exist. The `open()` call fails with `FileNotFoundError: [Errno 2] No such file or directory: '/tmp/fake_editor.md'` because the directory component of the path is nonexistent.

The fix is to move the `editor_cmd` check BEFORE the temp file creation block, so that if no editor is configured, the method returns `""` early without attempting any file operations.

### Discrepancies
- `_launch_editor_background` returns `""` when `editor_cmd` is None, which should pass the test assertion. Yet the test fails. This suggests an exception is raised before the early-return. (Resolved: The exception is a `FileNotFoundError` raised by `open(temp_path, "w", ...)` when `temp_path` is `"/tmp/fake_editor.md"` on Windows. The method creates the temp file before the early-return check, so the crash occurs before `return ""` is ever reached.)

### Investigation History
1. Initial report: CI failure on Windows in `test_no_editor_returns_empty_string_and_logs`.
   - Observation: `_launch_editor_background` creates temp file before checking for editor.
   - Conclusion: Temp file creation is primary suspect; log extraction pending to confirm.
2. CI log extraction: `gh run view --log-failed` returned Quality Checks logs, not Windows test logs.
   - Action: Extract specifically from "Run Tests" step using awk filtering.
   - Result: Extracted exact error — `FileNotFoundError: [Errno 2] No such file or directory: '/tmp/fake_editor.md'`.
3. Local MRE at `spikes/debug/31-windows-editor-mre.py` confirmed macOS passes.
   - Observation: On macOS, `open("/tmp/fake_editor.md", "w")` succeeds because `/tmp` exists.
4. CI log analysis — confirmed exact exception and cause.
   - Observation: The error occurs at line 194 (`open(temp_path, "w", encoding="utf-8")`) inside the temp file creation block, which runs before the `if not editor_cmd:` early return.
   - Conclusion: The fix is to move the `editor_cmd` check before the temp file creation block.
5. Shadow file verification (`spikes/debug/shadow_console_interactor_ask_loop.py`):
   - Fix applied: moved `editor_cmd = self._tooling.find_editor()` and the `if not editor_cmd:` early return to the top of `_launch_editor_background`, before any temp file operations.
   - MRE updated to target shadow module (patching shadow module's `sys.stdin.isatty`, `_flush_stdin`, and `logger.info`).
   - Execution: `uv run python spikes/debug/31-windows-editor-mre.py` — **MRE PASSED** (returned empty string and logged correctly).
   - Conclusion: The fix is empirically proven without touching production code.

## Solution

### Root Cause
`_launch_editor_background` in `console_interactor_ask_loop.py` creates a temp file via `self._system_env.create_temp_file()` **before** checking if an editor is configured (`if not editor_cmd:`). The test mock returns the POSIX path `"/tmp/fake_editor.md"`. On Windows, `/tmp` does not exist, so `open(path, "w")` raises `FileNotFoundError` before the early return is reached.

### Proven Fix
Move the `editor_cmd = self._tooling.find_editor()` check to the **top** of `_launch_editor_background`, before any file operations. If no editor is configured, return `""` immediately. This avoids wasteful temp file creation and prevents the Windows crash. Verified via shadow file (`spikes/debug/shadow_console_interactor_ask_loop.py`) — MRE passed.

### Systemic Preventative Measures
1. **Fix the same anti-pattern in `console_interactor.py`**: The `_launch_editor` method at line 95 creates a temp file before calling `find_editor()` at line 100. Apply the same reorder (check editor first).
2. **Establish a coding standard**: "Any resource creation (file, network, memory) MUST be preceded by validation of all preconditions that could make the resource unnecessary." This prevents future regressions where a method allocates resources before checking if they're needed.
3. **Cross-platform test path handling**: Test mocks that use hardcoded POSIX paths (`/tmp/fake_editor.md`) should use `tempfile.gettempdir()` or a test-specific temp directory (like `tmp_path` fixture) to ensure they work on all platforms.
4. **No other instances found**: Audit confirmed that `textual_plan_reviewer_editor.py`, `textual_plan_reviewer_previews.py`, and `console_interactor_helpers.py` do not have this ordering issue.