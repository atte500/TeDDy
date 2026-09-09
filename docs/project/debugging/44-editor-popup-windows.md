# Bug: Editor popup on `v`/`m` keypress on Windows
- **Status:** Unresolved
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
`launch_editor()` in `textual_plan_reviewer_editor.py` runs `subprocess.run([editor, filepath])` inside Textual's `app.suspend()` context manager. On Unix, `app.suspend()` sends SIGTSTP to suspend the Python process, allowing the editor to take foreground control. On Windows, there is no SIGTSTP mechanism — the editor process spawns as a child but the TUI process does not properly yield the foreground. The editor may launch in the background (no visible window) or fail silently, resulting in the "popup" effect.

**No platform-specific handling exists anywhere in the editor code path.** Specifically:
- No `CREATE_NO_WINDOW` flag on `subprocess.run` (which would prevent the blank popup on Windows).
- No `os.startfile()` fallback (which opens files with the associated application on Windows).
- No `_is_windows` / `platform.system()` branch anywhere in the code path.
- No `subprocess.CREATE_NEW_CONSOLE` or similar Windows process creation flags.

### Discrepancies
- None — the causal model fully explains the observed symptoms.

### Investigation History
1. Confirmed BINDINGS: `v` → `view_plan`, `m` → `add_message` in `textual_plan_reviewer_app.py`.
2. Traced `view_plan` action → calls `launch_editor()` in `textual_plan_reviewer_editor.py`.
3. `launch_editor()` uses `subprocess.run` inside `app.suspend()`.
4. Grep confirmed zero platform-specific branching (`platform.system()`, `sys.platform`, `os.name`) in the pre-request pipeline.
5. Grep confirmed zero `CREATE_NO_WINDOW` usage anywhere in the codebase.

## Solution

### Root Cause
The recent READ preview refactor (commit `13c127dd`) unified file opening through `launch_editor()`, which relies on Unix-`only `app.suspend()` mechanics. Windows has no equivalent suspend/resume mechanism, so the editor spawns in the background without a visible window, causing the "popup" effect.

### Proven Fix
TBD by Debugger investigation. Options include:
- Add `platform.system()` branching in `launch_editor()`: use `subprocess.run(CREATE_NO_WINDOW)` or `os.startfile()` on Windows.
- Refactor to avoid `app.suspend()` entirely on Windows.
- Use Textual's built-in `open_url` or `run_process` with platform-specific flags.

### Systemic Prevention
- All process-spawning code paths must include Windows platform handling (at minimum `CREATE_NO_WINDOW` or `os.startfile` pattern).
- Add pre-commit hook or CI check to flag `app.suspend()` usage without Windows guard.
- Add Windows integration tests for TUI editor workflows.
