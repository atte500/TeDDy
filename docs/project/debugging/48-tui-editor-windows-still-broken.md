# Bug: TUI editor ('m', 'v', 'e') fails to open GUI editor on Windows

- **Status:** Resolved
- **Milestone:** N/A (Ad-hoc regression from recent commits)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

**Expected behavior:** Pressing `v` (view plan), `m` (add message), or `e` (edit action param requiring external editor) in the TUI opens the configured external editor (e.g., Codium) with the relevant file.

**Actual behavior on Windows:** A toast notification appears saying "Opening Editor: codium.CMD", but the editor window does not appear. The application remains in the TUI with no usable editor window. However, pressing `e` in the **console ask loop** (non-TUI mode) still works correctly and opens Codium.

**Minimal reproduction:** Run TeDDy TUI on Windows. Press `v`, `m`, or `e` on an action requiring an external editor. Observe the toast notification but no editor window.

## Context & Scope

### Regressing Delta
The regression was introduced incrementally across two commits:
1. `14abbbab` "fix(tui): add Windows platform branching to launch_editor and preview_edit_diff_viewer" — first added platform-specific code.
2. `8e10164e` "fix(tui): differentiate CLI vs GUI editors on Windows for launch_editor and preview_edit_diff_viewer" — refactored to add `_run_editor_process()` helper and updated `spawn_editor()` to use `CREATE_NO_WINDOW` on Windows.

The problematic change: `spawn_editor()` in `textual_plan_reviewer_editor.py` (lines ~44-48) was updated to pass `creationflags=subprocess.CREATE_NO_WINDOW` when `sys.platform == "win32"`. This flag suppresses the console window which is required for batch files (`.CMD`/`.BAT`) to execute properly. Batch-wrapped editors like `codium.CMD` fail silently when run without a console window.

### Environmental Triggers
- Windows OS (any version supported by the application)
- TUI mode (TextualPlanReviewer)
- Editor configured as a batch file wrapper (e.g., `codium` which resolves to `codium.CMD`, `code` which resolves to `code.CMD` on some installations)
- The console ask loop path (`console_interactor_ask_loop.py`) does NOT use `CREATE_NO_WINDOW` and works correctly.

### Ruled Out
- Not a Linux/Mac issue — the `CREATE_NO_WINDOW` flag is only applied on Windows.
- Not a "missing editor config" issue — the toast confirms the editor command is resolved.
- Not a suspend/resume issue — GUI editors go through `spawn_editor()`, not `app.suspend()`.
- Not specific to Codium — any editor installed via a batch wrapper (common with Microsoft-managed installers) would be affected.

## Diagnostic Analysis

### Causal Model (Verified)
The TUI editor launch chain fails on Windows (and any platform where Textual wraps `sys.stdin`) because of explicit handle redirection:

1. User presses `v`/`m` → `view_plan()`/`add_message()` → `launch_editor()`.
2. `launch_editor()` checks editor availability → calls `find_editor()`.
3. If editor is a GUI editor (not in `_CLI_EDITORS` set), it calls `spawn_editor(editor_cmd, temp_file)`.
4. `spawn_editor()` passes `stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr` to `subprocess.Popen()`.
5. In Textual's TUI, `sys.stdin` is replaced with a custom wrapper (TextualStdin) that **does not expose a valid file descriptor** – calling `fileno()` raises an `AttributeError`.
6. When `Popen` receives `stdin=sys.stdin`, it tries to call `fileno()` to duplicate the handle, which raises `AttributeError`. The bare `except Exception` in `spawn_editor()` catches this error and logs it at DEBUG level, but **the process never starts**.
7. The toast notification fires before the spawn call, so the user sees "Opening Editor" but the editor never appears.
8. The working path (`console_interactor_ask_loop.py` → `_launch_editor_background()`) uses `subprocess.Popen(editor_cmd + [temp_path])` with **no explicit redirection**, so `Popen` inherits the parent's actual console handles and works correctly.

**The fix:** Remove the explicit `stdin`, `stdout`, `stderr` parameters from all subprocess calls in the TUI editor code paths. This matches the pattern used by the working console ask loop.

### Discrepancies
- ~~The console ask loop works without `CREATE_NO_WINDOW`, but the TUI uses it.~~ (Resolved: `CREATE_NO_WINDOW` is NOT the cause. Turn 08 proved all three spawn patterns succeed from normal Python. The real difference is the explicit `stdin`/`stdout`/`stderr` redirection.)
- ~~Case File #44 (Resolved) explicitly added `CREATE_NO_WINDOW` to fix a "popup" issue.~~ (Resolved: `CREATE_NO_WINDOW` does not block the editor – it suppresses the console window flash for batch files. It is not harmful and stays.)
- **Root cause identified:** Passing `stdin=sys.stdin` to `subprocess.Popen` fails when `sys.stdin` lacks a valid file descriptor, which occurs inside Textual's TUI event loop. This is confirmed by Turn 09's probe.

### Investigation History
1. (Turn 01) Checked git log — identified commits `8e10164e` and `14abbbab` as the regressing delta for Windows editor handling.
2. (Turn 02) Read `textual_plan_reviewer_editor.py`, `console_interactor_ask_loop.py`, `console_tooling.py`, and Case Files #44, #47.
3. (Turn 03 - Validation Failure) Attempted to create Case File and MRE but plan was rejected due to missing content code blocks.
4. (Turn 04) Created Case File and MRE. (Success)
5. (Turn 05) Executed MRE on Windows 11. Results: Both with and without CREATE_NO_WINDOW failed with WinError 193. Disproved initial CREATE_NO_WINDOW hypothesis.
6. (Turn 06 - Validation failure) Failed to probe editor path resolution due to shell syntax.
7. (Turn 07) Created and executed `48-probe-editor-path.py`. Inconclusive (DEVNULL used for all streams).
8. (Turn 08) Created and executed `48-reprobe-exact-popen.py`. **All three modes succeeded (editor opened).** Disproved the `CREATE_NO_WINDOW` hypothesis.
9. (Turn 09) Created and executed `48-probe-textual-stdin.py`. **Baseline (real stdin, redirection) succeeded. TUI-like (no fileno, with redirection) FAILED with AttributeError. TUI-like (no fileno, WITHOUT redirection) SUCCEEDED.** Root cause identified: passing explicit `stdin=sys.stdin` to Popen fails in TUI because Textual's stdin lacks fileno().
10. (Turn 10) Alignment: user confirmed the analysis ("ok proceed").
11. (Turn 11) Systemic Audit: identified all 6 affected call sites via git grep.
12. (Turn 12-17) Shadow files created; verification script iterated and fixed.
13. (Turn 18) Inline verification script passed: zero-touch fix confirmed.
15. (Turn 19-23) Applied fixes to production code (6 call sites), updated/addressed 4 regression tests (3 updated, 1 new) plus 1 new test file (`test_tui_editor_stdin_fileno_regression.py`).
16. (Turn 24-28) Acceptance test updated, spike files cleaned, Case File finalized with Resolved status.
17. (Turn 29-30) Full test suite verified (1198 passed, 24 skipped). Committed via VCP.

## Solution

### Root Cause
Inside the Textual TUI, `sys.stdin` is replaced by a custom wrapper that lacks a valid `fileno()` method (raises `AttributeError`). When `spawn_editor()`, `launch_editor()` (CLI path), `preview_edit_diff_viewer()` (CLI path), and `run_command(background=True)` pass `stdin=sys.stdin`, `stdout=sys.stdout`, and `stderr=sys.stderr` to `subprocess.Popen` or `_run_editor_process()`, the call fails because `Popen` tries to duplicate the file descriptor. The bare `except Exception` in `spawn_editor()` catches this error silently, and the editor never launches, despite the toast notification appearing.

The console ask loop works because it calls `Popen()` **without** explicit `stdin`/`stdout`/`stderr` parameters, allowing the child process to inherit the actual console handles.

### Proven Fix
Remove the explicit `stdin=sys.stdin`, `stdout=sys.stdout`, `stderr=sys.stderr` from all subprocess calls in the TUI editor code paths. This matches the pattern used by the working console ask loop and ensures `Popen` inherits the parent's real console handles.

**Affected locations (all updated):**
- `textual_plan_reviewer_editor.py`:
  - `spawn_editor()`: removed explicit stdio kwargs from `subprocess.Popen()`.
  - `launch_editor()` Windows CLI path: removed explicit stdio from `_run_editor_process()` call.
  - `launch_editor()` Unix CLI path: removed explicit stdio from `_run_editor_process()` call.
  - `preview_edit_diff_viewer()` Windows CLI path: removed explicit stdio from `_run_editor_process()` call.
  - `preview_edit_diff_viewer()` Unix CLI path: removed explicit stdio from `_run_editor_process()` call.
- `system_environment_adapter.py`:
  - `run_command()` background path: removed explicit stdio from `subprocess.Popen()`.

### Verification
- Turn 09 probe proved the mechanism: simulating Textual's stdin (no fileno) caused `AttributeError` with redirection, but succeeded without.
- Turn 18 inline verification script confirmed the fix works empirically for both `spawn_editor` and `run_command(background=True)`.
- Regression tests:
  - `test_system_environment_adapter_kwargs.py`: 5 tests verify `run_command(background=True)` does not pass explicit stdio kwargs.
  - `test_tui_editor_stdin_fileno_regression.py`: `test_spawn_editor_no_attribute_error_when_stdin_lacks_fileno()` verifies `spawn_editor()` does not raise AttributeError.
- Full test suite passes after applying the fix.

### Systemic Prevention
- Any future subprocess calls that require handle inheritance from the parent should **not** pass explicit `sys.stdin`/`sys.stdout`/`sys.stderr`. The regression tests serve as living documentation of this pattern.
