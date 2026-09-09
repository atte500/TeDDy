# Bug: Editor popup on `v`/`m` keypress on Windows
- **Status:** Resolved
- **Milestone:** N/A (Ad-hoc regression from recent commit)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

**Expected behavior:** Pressing `v` (view plan) or `m` (add message) in the TUI opens the plan file in the configured external editor.

**Actual behavior on Windows:** The editor appears to "pop up" briefly (a window flash) but does NOT open the file or display the editor window. The user sees a popup effect with no usable editor window. The editor process likely spawns in the background with no visible window.

**Minimal reproduction:** Run TeDDy TUI on Windows. Press `v` or `m`. Observe the editor popup with no visible file.

## Context & Scope

### Regressing Delta
Commit `13c127dd` ("fix(tui): route READ preview through launch_editor for vim color consistency") changed how `v` (`view_plan`) and `m` (`add_message`) keypresses in the TUI open files. Previously, the actions opened files directly via a platform-aware mechanism. The commit refactored the preview to route through `launch_editor()`.

The code path:
1. BINDINGS in `textual_plan_reviewer_app.py` map `v` → `view_plan`, `m` → `add_message`.
2. `view_plan` action calls `launch_editor()` in `textual_plan_reviewer_editor.py`.
3. `launch_editor()` uses `subprocess.run` inside `app.suspend()`.

### Environmental Triggers
- Windows OS (any version supported by the app)
- TUI mode (Textual app running in terminal)
- `editor` config value set to any editor (or default)

### Ruled Out
- Not a Linux/Mac issue — Unix suspend/resume via SIGTSTP works correctly.
- Not a specific editor issue — no Windows editor would work through this code path.
- Not a missing config issue — even with editor unset/empty, the code path triggers.

## Diagnostic Analysis

### Causal Model
`launch_editor()` and `preview_edit_diff_viewer()` in `textual_plan_reviewer_editor.py` run `subprocess.run([editor, filepath])` inside Textual's `app.suspend()` context manager. On Unix, `app.suspend()` sends SIGTSTP to suspend the Python process, allowing the editor to take foreground control. On Windows, there is no SIGTSTP mechanism — the editor process spawns as a child but the TUI process does not properly yield the foreground. The editor may launch in the background (no visible window) or fail silently, resulting in the "popup" effect.

**Both functions now have correct platform-specific handling after DRY/KISS refactoring:**

A centralized helper `_run_editor_process()` adds `subprocess.CREATE_NO_WINDOW` on Windows for synchronous `subprocess.run` calls. `spawn_editor()` also adds `CREATE_NO_WINDOW` when called on Windows for GUI editor background spawning.

- `launch_editor()`:
  - **CLI editors on Windows:** synchronous `_run_editor_process()` with `creationflags=CREATE_NO_WINDOW`, no `app.suspend()`.
  - **CLI editors on Unix:** `with app.suspend(): _run_editor_process()` — unchanged behavior.
  - **GUI editors (any platform):** `spawn_editor()` (with `CREATE_NO_WINDOW` on Windows) + `ConfirmScreen` harvest.
- `preview_edit_diff_viewer()`:
  - **CLI editors on Windows:** same as launch_editor — `_run_editor_process()` + restore.
  - **CLI editors on Unix:** `with app.suspend(): _run_editor_process()` — unchanged.
- The `_restore_foreground_process_group()` already had a `sys.platform == "win32"` guard.

### Discrepancies
- None — the causal model fully explains the observed symptoms.

### Investigation History
1. Confirmed BINDINGS: `v` → `view_plan`, `m` → `add_message` in `textual_plan_reviewer_app.py`.
2. Traced `view_plan` action → calls `launch_editor()` in `textual_plan_reviewer_editor.py`.
3. `launch_editor()` uses `subprocess.run` inside `app.suspend()`.
4. Grep confirmed zero platform-specific branching (`platform.system()`, `sys.platform`, `os.name`) in the pre-request pipeline.
5. Grep confirmed zero `CREATE_NO_WINDOW` usage anywhere in the codebase.
6. **Shadow File Zero-Touch Verification (Turn 9-12):** Created `shadow_textual_plan_reviewer_editor.py` with Windows branch using `subprocess.run(creationflags=CREATE_NO_WINDOW)` and no `app.suspend()`. The MRE mocked `sys.platform = "win32"` and confirmed: app.suspend() NOT called, subprocess.run called with creationflags=134217728. Local MRE passed with exit code 0.
7. **Systemic Audit (Turn 15):** Grep found two `with app.suspend():` locations: `launch_editor()` (line 311) and `preview_edit_diff_viewer()` (line 406). Both lack Windows platform guards. The same platform branching fix applied to both.
8. **First Fix (Turn 19):** Added `sys.platform == "win32"` branching but placed it BEFORE the CLI/GUI check, routing ALL editors on Windows through synchronous `subprocess.run(creationflags=CREATE_NO_WINDOW)`. This broke GUI editors (e.g. codium.CMD) which needed background Popen + ConfirmScreen.
9. **DRY/KISS Refactoring (Turn 27):** Added `_run_editor_process()` helper that centralizes `creationflags` logic. Updated `spawn_editor()` to add `CREATE_NO_WINDOW` on Windows for GUI editors. Refactored `launch_editor()` to check CLI vs GUI FIRST, then platform: CLI editors on Windows use sync `_run_editor_process()`, GUI editors on any platform use `spawn_editor()` + ConfirmScreen. `preview_edit_diff_viewer()` updated to use the helper. Regression tests added for both CLI and GUI editors on Windows.
10. **CI Test Fixes (Turn 31):** Windows CI reported 5 test failures caused by existing tests assuming Unix-only suspend/resume behavior:
    - `test_view_plan_works_with_no_path_but_in_memory_content` — Popen assertion missing `creationflags` on Windows; updated to conditionally include it.
    - `test_flush_called_after_suspend_exit` and `test_flush_called_after_suspend_exit_with_exception` — marked `skipif(win32)` since they test suspend/flush ordering not applicable on Windows.
    - `test_restoration_functions_called_inside_suspend` — marked `skipif(win32)` since Windows doesn't use `app.suspend()`.
    - `test_cli_editor_triggers_suspend` — marked `skipif(win32)` since CLI editors on Windows use synchronous `_run_editor_process()` without `app.suspend()`.

## Solution

### Root Cause
Commit `13c127dd` refactored file opening to route through `launch_editor()`, which relies on Unix-only `app.suspend()` mechanics. Windows has no equivalent suspend/resume mechanism (SIGTSTP), so the editor spawns in the background without a visible window, causing the "popup" flash. The same issue exists in `preview_edit_diff_viewer()` (line 406).

### Proven Fix (DRY/KISS Refactoring)

Added a centralized `_run_editor_process()` helper that adds `subprocess.CREATE_NO_WINDOW` on Windows for synchronous subprocess.run calls. Updated `spawn_editor()` to add `CREATE_NO_WINDOW` on Windows for background GUI editor spawning. Refactored `launch_editor()` to check CLI vs GUI first, then platform:

- **Windows CLI editors (vim, nvim, nano):** `_run_editor_process(cmd, creationflags=CREATE_NO_WINDOW)` — no `app.suspend()`, no blank popup. Returns edited content after editor exits.
- **Windows GUI editors (codium.CMD, code, cursor):** `spawn_editor()` with `CREATE_NO_WINDOW` + `ConfirmScreen` harvest — same pattern as Unix GUI editors but with the popup suppressed.
- **Unix CLI editors:** unchanged — `with app.suspend(): _run_editor_process(...)` with terminal restore.
- **Unix GUI editors:** unchanged — `spawn_editor()` + ConfirmScreen.

Similarly, `preview_edit_diff_viewer()` uses `_run_editor_process()` for its Windows CLI editor path.

Verified via:
- Combined probe (CLI and GUI editors on Windows both behave correctly).
- Regression tests `test_launch_editor_windows_use_create_no_window` and `test_launch_editor_windows_gui_editor_uses_spawn` in `test_tui_editor_suspend_resume.py`.
- Full test suite (1211 passed, 5 skipped).

### Systemic Prevention
- All process-spawning code paths now use `_run_editor_process()` or `spawn_editor()` with platform-appropriate flags.
- A pre-commit hook or CI check could be added to flag any new `app.suspend()` usage without a Windows guard (future improvement).
- Windows CI runs for the TUI test suite will catch regressions.
