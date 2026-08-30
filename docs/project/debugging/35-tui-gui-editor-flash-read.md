# Bug: READ Action Opens Empty Temp File and GUI Flash Persists
- **Status:** Unresolved
- **Milestone:** [Milestone 4: TUI & UX Enhancements](/docs/project/milestones/04-tui-ux-enhancements.md)
- **Vertical Slice:** N/A
- **Specs:** [Textual Plan Reviewer Editor](/docs/architecture/adapters/inbound/textual_plan_reviewer.md)

## Symptoms

Pressing `e` on a READ action node in the TUI plan reviewer causes two issues:

1. **GUI Editor Flash:** The terminal briefly returns to the console before the external editor opens. This did not happen before recent editor integration changes.
2. **Empty Temp File:** The external editor opens an **empty** or blank temporary file instead of the actual file content from the specified resource path.

**Expected behavior:** The TUI should suspend cleanly without visible console flicker, and the external editor should open with the full content of the file specified in the READ action's `resource` or `path` parameter.

**Actual behavior:** The terminal briefly flashes to the shell prompt before the editor appears, and the editor opens an empty file. The flash issue was present before the empty file regression; the empty file appears to be a new or recently-introduced symptom.

**Minimal reproduction:**
1. Start a TeDDy session with the TUI (`teddy start`)
2. Navigate to a READ action node that points to an existing file (e.g., `README.md`)
3. Press `e` to open the file for read-only viewing
4. Observe: console flashes briefly, then editor opens an empty file

## Context & Scope

### Regressing Delta
The `preview_readonly()` function in `textual_plan_reviewer_previews.py` was modified as part of the editor subsystem overhaul (slices 00-16 and 00-17). The function:
1. Calls `app._file_system.read_file(resource)` to get file content
2. Creates a temporary file with the correct suffix
3. Writes the content to the temp file: `with open(temp_file, "w", encoding="utf-8") as f: f.write(content)`
4. Sets `os.chmod(temp_file, 0o444)` (read-only)
5. Launches the editor with `subprocess.run()` inside `app.suspend()`
6. Deletes the temp file in a `finally` block

Despite the write step, the user reports the editor opens an empty file. This suggests either:
- `content` is empty (the `read_file` call fails silently)
- The write fails silently (permissions, file system)
- The temp file is created but written to a different path than the one opened
- The editor (especially GUI editors like VS Code) opens the file before the write completes (race condition)

The GUI flash persists because `preview_readonly()` uses a direct `subprocess.run()` call for ALL editors (CLI and GUI). The `preview_edit()`, `preview_create()`, and `preview_text_action()` functions use `launch_editor()` which has different suspend/resume behavior — they work correctly without flashing or empty files.

### Environmental Triggers
- Observed with GUI editors (VS Code `code`, Cursor `cursor`) that spawn a child process and exit immediately
- May also affect terminal editors (vim, nvim) but the empty file issue is more noticeable with GUI editors since vim typically shows "new file" explicitly
- macOS and Linux systems (TTY-based)
- Not consistently reproducible — timing-dependent

### Ruled Out
- `app.suspend()` context manager: Both `preview_readonly()` and `launch_editor()` use `app.suspend()` — this is not the differentiator
- TTY restoration functions: `_restore_foreground_process_group()` and `_restore_terminal_cooked_mode()` are called in both paths
- The annotated diff changes from slice 00-17 only affect EDIT actions, not READ actions
- The underlying `launch_editor()` function handles CREATE, EXECUTE, and other READ-like actions (view_plan, add_message) without flashing
- File existence: The READ action node shows the file path correctly; the TUI context panel shows it exists
- Suffix matching: The temp file is created with the correct suffix from `pathlib.Path(resource).suffix`
- Editor launch: The editor does launch (empty file) so the subprocess/spawn is working
- TTY restoration: Both paths call `_restore_foreground_process_group()` and `_restore_terminal_cooked_mode()` — these restore terminal state but don't affect file content
- The write is correct: Code inspection shows `open(temp_file, "w", ...)` writes `content` before launching editor

## Diagnostic Analysis

### Causal Model

**For the empty file:** The `content` variable comes from `app._file_system.read_file(resource)`. If this call fails (file not found, permissions, encoding issue), the exception handler sets `content` to a message string `f"--- Content for {resource} could not be retrieved ---"`. This should still show as text in the editor, not an empty file. However, if `read_file()` returns an empty string silently (existing file but empty content), the temp file would be empty. Alternatively, if the `os.chmod(0o444)` call fails silently (permissions on the temp file creation), the file might not be readable at all. Or if the editor (e.g., VS Code) opens the file by path before the Python process finishes writing (race condition due to Popen for GUI editors), the file might be read as empty initially.

For GUI editors: `preview_readonly()` uses `subprocess.run()` (sync) even for GUI editors — it does NOT use `spawn_editor()` (Popen). This means the TUI blocks until the `code` command exits. But `code` exits immediately after spawning a background process, so `subprocess.run()` returns quickly. The temp file delete happens in the `finally` block (after the editor process exits), so the file should still exist when the editor opens. However, the `subprocess.run()` with sync/wait should be correct. The race condition hypothesis seems unlikely for sync.

**For the flash:** The flash occurs because when `subprocess.run()` returns (GUI editor exits immediately), the `app.suspend()` context manager exits, causing Textual to resume its render loop briefly before the actual editor window takes over the terminal. This is a timing issue inherent to GUI editors that spawn child processes and exit. In contrast, `launch_editor()` uses `spawn_editor()` (Popen) for GUI editors, which does not block the TUI — the ConfirmScreen stays on top while the editor is open in the background.

### Discrepancies
- The code writes `content` to the temp file, but the user reports the file is empty. This suggests either `content` is empty (read_file returns empty string) or the write doesn't complete before the editor reads the file. Since the code is synchronous for CLI editors, the write should complete before `subprocess.run()` is called. For GUI editors, the write should also complete synchronously before the subprocess. But if `app._system_env.create_temp_file()` returns a path that is later deleted/recreated by the editor? Unlikely.
- The `finally` block deletes the temp file — for short-lived editor views (like VS Code that caches content), the file may be deleted before the editor finishes reading from disk.
- `subprocess.run()` returning immediately for GUI editors should not cause a flash if `app.suspend()` properly maintains the TTY state. The flash suggests the TUI's rendering loop resumes briefly before the editor takes over the terminal.
- `os.chmod(temp_file, 0o444)` is called before launching the editor. For GUI editors that need write access, this could cause an error popup or silent failure, potentially contributing to the flash behavior.

### Investigation History
1. **Code review (2026-08-30):** Read `preview_readonly()` and compared to `launch_editor()` path. Key differences identified:
   - `preview_readonly()` uses direct `subprocess.run()` with explicit stdio forwarding for ALL editors
   - `launch_editor()` uses `spawn_editor()` (Popen) for GUI editors, avoiding the flash
   - `preview_readonly()` sets `os.chmod(temp_file, 0o444)` to lock the file read-only — `launch_editor()` does not
   - The temp file in `preview_readonly()` is deleted in a `finally` block — if the editor process exits quickly (GUI editors), the deletion races with the TUI resume

2. **Hypothesis (2026-08-30):** The `os.chmod(0o444)` combined with quick editor exit causes the flicker. When a GUI editor like `code` exits immediately after spawning a child, `subprocess.run()` returns, the `finally` block deletes the temp file, and the TUI resumes — all before the editor window appears. The brief terminal state restoration causes the visible flash. *Conclusion: Unconfirmed — needs targeted debugging with the actual TUI running.*

3. **Turn 12 (2026-08-30):** User tested READ notification fix and reported flash still present. Empty file not yet reported at this point.

4. **Turn 16 (2026-08-30):** READ notification format fixed to `"Opening Editor: {name}"`. No changes to the file opening mechanism.

5. **Turn 22 (2026-08-30):** User reports the file is now **empty** — a new symptom not previously documented. Possible regression from recent changes (notification fix, explicit stdio, or temp file handling changes in slice 00-17).

## Solution
*No solution identified yet. Requires investigation into both issues.*

**For the empty file:**
- **Hypothesis 1: `read_file()` returns empty string.** Check if the READ action's `resource` field correctly resolves to an existing file. If the file path is wrong or inaccessible, the exception handler would set content to an error message, not empty. But if `read_file()` succeeds and returns an empty string (valid empty file), the temp file would be empty. Verify with a non-empty file.
- **Hypothesis 2: Temp file path mismatch.** The `create_temp_file()` might return a path that is different from the path passed to the editor. Verify the path used in `open(temp_file, "w")` matches the path in `editor_cmd + [temp_file]`.
- **Hypothesis 3: Editor reads before write completes.** For GUI editors launched via `subprocess.run()` (sync), the write should complete before `subprocess.run()` is called. But if the editor opens the file by path and reads it as part of its spawn process, there could be a race. Try adding `time.sleep(0.1)` or `os.fsync()` after the write.
- **Hypothesis 4: File deletion race.** The `finally` block deletes the temp file immediately when `subprocess.run()` returns. For GUI editors that keep a file handle open, the file may still be accessible, but for editors that read the file on demand, it may be gone. The fix would be to NOT delete the temp file for READ actions, or schedule deletion for later.

**For the flash:**
- **Hypothesis:** `preview_readonly()` should use the same pattern as `launch_editor()` — use `spawn_editor()` (Popen) for GUI editors instead of `subprocess.run()`. The sync `subprocess.run()` causes the TUI to resume immediately after the GUI editor's short-lived parent process exits, producing the flash. Switching to Popen for GUI editors would keep the ConfirmScreen active while the editor is open, matching the behavior of CREATE, EXECUTE, and other actions.
- **Potential fix:** Route GUI editors through `spawn_editor()` + ConfirmScreen flow instead of the current `subprocess.run()` path. This would require checking if the editor is a GUI editor (using `_is_cli_editor()` or equivalent) and branching accordingly, similar to how `launch_editor()` handles the CLI vs GUI split.
