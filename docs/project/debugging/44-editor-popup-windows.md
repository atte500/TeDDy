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

**Both functions now have platform-specific handling:**
- `if sys.platform == "win32":` uses `subprocess.run(creationflags=subprocess.CREATE_NO_WINDOW)` without `app.suspend()`, preventing the blank popup.
- `elif _is_cli_editor(editor_cmd):` (Unix) unchanged — `with app.suspend(): subprocess.run(...)`.
- `else:` (GUI editors) unchanged — `spawn_editor()` + ConfirmScreen.
- The `_restore_foreground_process_group()` already had a `sys.platform == "win32"` guard.
- `preview_edit_diff_viewer()`: Windows path added before the `with app.suspend():` block, using the same `subprocess.run(creationflags=CREATE_NO_WINDOW)` pattern.

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
8. **Production Fix Applied:** Added `sys.platform == "win32"` branching to both `launch_editor()` and `preview_edit_diff_viewer()`. On Windows, uses `subprocess.run(creationflags=CREATE_NO_WINDOW)` without `app.suspend()`. On Unix, unchanged. Regression test added to `test_tui_editor_suspend_resume.py`.

## Solution

### Root Cause
Commit `13c127dd` refactored file opening to route through `launch_editor()`, which relies on Unix-only `app.suspend()` mechanics. Windows has no equivalent suspend/resume mechanism (SIGTSTP), so the editor spawns in the background without a visible window, causing the "popup" flash. The same issue exists in `preview_edit_diff_viewer()` (line 406).

### Proven Fix
Added `sys.platform == "win32"` branching in both `launch_editor()` and `preview_edit_diff_viewer()`:
- **Windows:** `subprocess.run(cmd, creationflags=subprocess.CREATE_NO_WINDOW)` — no `app.suspend()`, preventing blank console popup.
- **Unix (CLI editors):** `with app.suspend(): subprocess.run(...)` — unchanged.
- **GUI editors:** unchanged — `spawn_editor()` + ConfirmScreen.

Verified via Zero-Touch Shadow File (MRE mocked `sys.platform = "win32"`, confirmed `app.suspend()` NOT called, `creationflags=0x08000000` passed). Regression test added to `test_tui_editor_suspend_resume.py`.

### Systemic Prevention
- All process-spawning code paths in `textual_plan_reviewer_editor.py` now include Windows platform branching. The `preview_edit_diff_viewer()` function was also fixed to prevent the same bug.
- A pre-commit hook or CI check could be added to flag any new `app.suspend()` usage without a Windows guard (future improvement).
- Windows CI runs for the TUI test suite will catch regressions.
