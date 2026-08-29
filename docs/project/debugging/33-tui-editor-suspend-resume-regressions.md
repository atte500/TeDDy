# Bug: TUI Plan Reviewer Editor Regressions (Ghost File, READ Warnings, Quit Staircase)

- **Status:** Unresolved
- **Milestone:** N/A (ad-hoc)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

Three distinct but likely related issues affect the TUI plan reviewer when using CLI editors (vim/nvim):

### Bug 1: EDIT action ghost file after diff viewer
**Expected:** Pressing `e` on an EDIT action opens a side-by-side diff view (vim -d). After saving and quitting, the user returns directly to the TUI.
**Actual:** After closing the diff view, the user is dropped into a second single-column editor (opening a single file) that must be exited before returning to the TUI. The extra editor appears to be another vim invocation with a single file argument.

### Bug 2: READ action editor warnings and "2 files to edit"
**Expected:** Pressing `e` on a READ action opens the file content in the editor. After exiting, the TUI continues normally.
**Actual:** The terminal briefly flashes back to console, showing:
- "2 files to edit" (or similar duplicate file message)
- "Vim: Warning: Input is not from a terminal"
After closing the editor, the TUI usually resumes.

### Bug 3: Quit staircase terminal shift
**Expected:** Pressing `q` to quit the TUI cleanly restores the terminal state.
**Actual:** After quitting, the terminal is in a "staircase" state — output is shifted horizontally with leftover characters from the last TUI render. The terminal appears partially corrupted.

## Context & Scope

### Regressing Delta
All three bugs involve the TUI's editor invocation flow through `app.suspend()`. The previous fixes (Case File #30, commits `aeeed302`, `f773f378`, `06836f63`) added process group and terminal restoration in `launch_editor()` and `preview_edit_diff_viewer()`, but the following code paths were not audited or use different patterns:

- **Bug 1 (EDIT ghost file):** `preview_edit_diff_viewer()` in `textual_plan_reviewer_editor.py` — CLI editors use `with app.suspend(): subprocess.run(...); _restore_fg(); _restore_cooked()`. The ghost file may originate from:
  - The `app.suspend()` context failing to restore the TUI, causing the user to see the terminal and mistakenly thinking a "ghost file" is open (actually the underlying shell).
  - An unhandled exception during suspension that causes the code to return `False` from `preview_edit_diff_viewer()`, falling through... but `preview_edit()` does NOT have a fallthrough to `launch_editor()` when `diff_viewer` is truthy. (Contradiction.)
  - The suspend/resume cycle corrupting the application state, causing Textual's event loop to process stale bindings or re-queue the edit action.
- **Bug 2 (READ action):** `preview_readonly()` in `textual_plan_reviewer_previews.py` — uses `app._system_env.run_command()` inside `app.suspend()`. `run_command()` uses `stdin=subprocess.DEVNULL` (detected via code analysis), causing vim's "Input is not from a terminal" warning. Additionally, unlike `launch_editor()` and `preview_edit_diff_viewer()`, `preview_readonly()` does NOT call `_restore_foreground_process_group()` or `_restore_terminal_cooked_mode()` after the command.
- **Bug 3 (Quit staircase):** The `action_cancel()` path calls `self.exit(None)` which triggers Textual's shutdown sequence. If the terminal state was corrupted by an earlier suspend/resume cycle (from Bug 1 or Bug 2), the final cleanup may be unable to restore it fully, producing the staircase effect.

### Environmental Triggers
- Requires a real TTY (not headless CI environment).
- Requires a CLI editor (vim, nvim) configured in `.teddy/config.yaml` or `VISUAL`/`EDITOR` env var.
- Reproducible on macOS (other Unix-like systems likely affected).
- Bug 2 specifically triggered by pressing 'e' on a READ action type.
- Bug 1 specifically triggered by pressing 'e' on an EDIT action type with a diff-viewer-enabled CLI editor (vim, nvim).

### Ruled Out
- The `_flush_stdin()` call is NOT inside the `app.suspend()` block in `launch_editor()` and `preview_edit_diff_viewer()` (this was the previous fix from Case File #30 and #00-09, confirmed via code read).
- The editor fallback chain (Task 00-16 fix) is not a factor — `find_editor()` correctly returns `None` when no editor is configured, but all three bugs occur with a properly configured editor.
- PTY isolation (Case File #28) was applied to the console ask loop (`console_interactor_ask_loop.py`), not the TUI paths. The TUI still uses direct TTY inheritance via `app.suspend()` → `subprocess.run()`.
- The "2 files to edit" in Bug 2 is NOT caused by the `editor_cmd` containing multiple files — code analysis shows `editor_cmd + [temp_file]` produces a single file argument. The message may be a misperception, a vim swap file warning, or an artifact of terminal corruption from a previous operation.

## Diagnostic Analysis

### Causal Model

**Common Thread:** All three bugs stem from incomplete or inconsistent terminal state management during the TUI's `app.suspend()` → editor → resume cycle.

#### Bug 1 (EDIT ghost file) — Hypothesis
```
preview_edit_diff_viewer → with app.suspend(): subprocess.run(vim -d before after)
                                                         ↓
                                   (suspend context may fail to properly hand over TTY)
                                                         ↓
                                   Textual's resume_application_mode() may not fully restore
                                   the alternate screen if the foreground process group
                                   was not correctly restored
```

The ghost file could be explained by:
1. **Suspend context failure:** If `app.suspend()` raises an exception during entry/exit, `preview_edit_diff_viewer` catches it with `except Exception` and returns `False`. However, `preview_edit()` does NOT open `launch_editor()` when `diff_viewer` is truthy regardless of return value. This contradicts a fallthrough theory.
2. **Terminal state confusion:** After the diff view, the user's terminal may show the underlying shell prompt. The user might see vim's temp file path or other terminal content and interpret it as "a single column file". But the report says they need to "exit from it again", suggesting an actual second vim session.
3. **Stale event processing:** After the suspend block, Textual's event loop may process a stale `on_list_view_selected` or similar event that triggers another editor opening. This requires investigation via MRE.

Key gap: There is no explicit second `subprocess.run()` or `launch_editor()` call in the EDIT + 'e' path. The extra editor must originate from an event handler or a race condition.

#### Bug 2 (READ action) — Hypothesis
```
preview_readonly → with app.suspend(): await anyio.to_thread.run_sync(
                     app._system_env.run_command, editor_cmd + [temp_file]
                   )
```

`run_command()` calls:
```python
subprocess.run(args, check=check, stdin=subprocess.DEVNULL)
```

**"Vim: Warning: Input is not from a terminal":** `stdin=subprocess.DEVNULL` means vim's stdin is `/dev/null`, not a TTY. Vim detects this and prints the warning. This happens because `run_command()` is designed for non-interactive background execution (it passes `stdin=DEVNULL`). Inside `app.suspend()`, vim should receive the actual TTY stdin. The fix should use `subprocess.run(args, stdin=sys.stdin)` or directly use the `subprocess.run()` pattern from `launch_editor()` instead of going through `run_command()`.

**"2 files to edit":** The command is `editor_cmd + [temp_file]` which produces a single file argument. Possible explanations:
- A vim swap file recovery prompt (misinterpreted as "2 files").
- Terminal corruption from a previous operation causing duplicate output.
- The `run_command()` TTY restore code (in `finally` block) runs `tcsetattr()` which may produce terminal output that vim reads as input.

Additionally, `preview_readonly()` does NOT call `_restore_foreground_process_group()` or `_restore_terminal_cooked_mode()` after the command, unlike `launch_editor()` and `preview_edit_diff_viewer()`. This means the terminal state may be left in raw mode or with a wrong foreground process group after vim exits inside the suspend block.

#### Bug 3 (Quit staircase) — Hypothesis
```
action_cancel → self.exit(None) → Textual shutdown → terminal restore
```

If any earlier suspend/resume cycle (Bug 1 or Bug 2) left the terminal in a partially restored state (e.g., raw mode still active, cursor position not reset), Textual's exit sequence will apply its own terminal reset. But if the terminal is in an unexpected state (e.g., cooked mode with echo off, or wrong cursor position), the reset may produce the staircase effect.

Staircase symptoms are classic of:
- Newline mode issues: terminal is in raw mode, so `\n` is not being converted to `\r\n`, causing lines to start at the current cursor column instead of column 0.
- Cursor positioning offset: if vim or the terminal emulator didn't fully restore cursor position, output drifts.

The likely chain: Bug 1 or Bug 2 partially corrupts terminal state → subsequent operations accumulate errors → 'q' exit triggers final restore which can't fully recover.

### Discrepancies
- Bug 1's ghost file conflicts with static analysis showing no fallthrough to `launch_editor()` when `diff_viewer` is truthy. Either the ghost file is not from `launch_editor()`, or there is an undiscovered code path. (Unresolved.)
- Bug 2's "2 files to edit" has no clear root cause given the single-file argument. It may be a vim behavior triggered by the non-TTY stdin or corrupted terminal state. (Unresolved.)
- Bug 3's staircase may be a symptom of Bug 1 or Bug 2 rather than an independent issue. All three need to be fixed together. (Hypothesis.)

### Investigation History
1. Initial triage: Read existing artifacts (Task 00-16, Case Files #28, #30, #31, #32). Three bugs not documented. User confirmed to investigate.
2. Code analysis (read all 4 TUI source files, 2 adapter files):
   - Confirmed `run_command()` uses `stdin=subprocess.DEVNULL` — explains Bug 2's terminal warning.
   - Confirmed `preview_readonly()` lacks process group/terminal restoration — contributor to Bug 2 and Bug 3.
   - Confirmed `preview_edit_diff_viewer()` and `launch_editor()` have correct restoration calls (fix from Case File #30).
   - Could NOT find a second editor invocation path for Bug 1 — suggests race condition or event loop issue.
3. Terminal mechanics analysis:
   - `_restore_foreground_process_group()` and `_restore_terminal_cooked_mode()` both use `except Exception: pass` — violates Failure Transparency rule. Debug logging would help.
   - `subprocess.run()` inside `app.suspend()` inherits the parent's TTY. The child (vim) can call `tcsetpgrp()` to claim foreground. On exit, it should restore, but macOS is known to leave the process group unchanged. The explicit restore in `launch_editor()` and `preview_edit_diff_viewer()` should fix this for those paths, but `preview_readonly()` lacks this fix.
4. Environment inspection:
   - The TUI runs inside Textual's application mode (alternate screen). When `app.suspend()` is entered, Textual saves the alternate screen, runs the subprocess, and on exit restores it. If the restore fails (e.g., because `tcsetattr` returns EIO), the user is left in the normal terminal buffer with corrupted settings.

## Solution

*This section will be populated by the Debugger after MRE-driven root cause analysis.*

### Expected Root Causes
1. **Bug 1:** Likely a race condition or event loop issue where the suspend/resume cycle causes Textual to re-queue an `edit_details` action. Could also be a screen-stack corruption where an extra modal is pushed during the suspend (e.g., `ConfirmScreen` from the GUI editor path incorrectly shown for CLI editor diff viewer).
2. **Bug 2:** `run_command()` inside `app.suspend()` uses `stdin=subprocess.DEVNULL` — needs to use real TTY stdin. Additionally, missing `_restore_foreground_process_group()` and `_restore_terminal_cooked_mode()` after the command.
3. **Bug 3:** Cumulative terminal state corruption from incomplete restoration. Fixing Bug 1 and Bug 2 should resolve this. Additional: add terminal state verification on exit.

### Investigative Plan (for Debugger)
1. **MRE for Bug 1:** Create a minimal Textual app that does `app.suspend()` → `subprocess.run(vim -d file1 file2)` → resume. Then simulate pressing 'e' again immediately and check if a second editor opens. Add logging to trace all `subprocess.run()` and `subprocess.Popen()` calls during the workflow.
2. **MRE for Bug 2:** Create a minimal Textual app that calls `run_command()` inside `app.suspend()` with a CLI editor. Verify that `stdin=DEVNULL` is the cause of the terminal warning. Also verify whether the missing restoration functions cause terminal state leakage.
3. **MRE for Bug 3:** Run a sequence of editor invocations (mix of EDIT and READ), then exit. Compare terminal state before and after. Check if cumulative state corruption correlates with number of suspend cycles.
4. **Verify Bug 1 suspicion:** Check if `preview_edit_diff_viewer` returns `True` or `False` in the scenario. If it returns `False`, confirm that `preview_edit()` still does not fall through to `launch_editor()`. If it returns `True`, the ghost file must come from another mechanism (event handler, binding re-fire, etc.).
5. **Check for stale event handlers:** After `app.suspend()` exits, Textual may re-process buffered events. If a `ListView.Selected` event is buffered from before the suspend, it could trigger `on_list_view_selected` which opens an editor via `handle_list_view_selected` → `ParameterEditModal`. Check if this is a `ListView` event path causing the ghost file.

### Proposed Fixes
1. **`preview_readonly()`**: Replace `app._system_env.run_command()` with direct `subprocess.run(editor_cmd + [temp_file], stdin=sys.stdin)` inside the suspend block. Add `_restore_foreground_process_group()` and `_restore_terminal_cooked_mode()` after the call.
2. **`preview_edit_diff_viewer()`**: Verify that the suspend block's exception handling does not mask failures that could cause ghost files. Add debug logging to all `except` branches.
3. **`action_cancel()`**: Add explicit terminal restoration (cooked mode + process group check) before `self.exit(None)` as a safety net.
4. **All suspend paths**: Log at debug level when `_restore_foreground_process_group()` and `_restore_terminal_cooked_mode()` are called, and any errors they encounter (currently silently swallowed).
5. **Systemic**: Audit all `app.suspend()` call sites in the codebase for consistent restoration patterns. Ensure all paths use the same three-step sequence: `subprocess.run()` → `_restore_fg()` → `_restore_cooked()`.
