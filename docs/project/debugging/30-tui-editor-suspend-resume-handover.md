# Bug: TUI Editor Suspend/Resume Handover - vim Exits to Console Instead of Returning to TUI
- **Status:** Resolved
- **Milestone:** N/A (ad-hoc)
- **Vertical Slice:** [00-09-tui-editor-suspend-resume](/docs/project/slices/00-09-tui-editor-suspend-resume.md)
- **Specs:** N/A

## Symptoms
**Expected:** Pressing `e` (edit) or `m` (message) in the TUI opens vim. After saving and quitting, the TUI screen should reappear with the edited content harvested. **Actual:** vim opens correctly. After exiting vim, the user is returned to the console (the TUI's alternate screen is not restored) and the process hangs indefinitely, apparently waiting for "TUI to finish plan review". The Console ask loop's editor path works correctly, confirming the TUI suspend/resume mechanism is the affected component.

**Minimal Reproduction Steps:**
1. Launch TUI (`teddy start` or via test harness).
2. Press `e` on any CREATE/EDIT action, or press `m`.
3. vim opens correctly with the expected content.
4. Write and quit vim (`:wq`).
5. **Bug:** The TUI does not reappear. The user sees the underlying console and the process appears to hang (no crash, no output).

## Context & Scope
### Regressing Delta
The bug appeared after the implementation of the 00-09 vertical slice (TUI Editor Suspend/Resume). Three commits are involved:
- `aeeed302` - Initial implementation of suspend/resume for CLI editors.
- `f773f378` - Added ConfirmScreen after CLI editor exit in launch_editor (reverted effect due to hotfix, see notes).
- `06836f63` - Moved ConfirmScreen to add_message_handler; moved _flush_stdin() inside the app.suspend() block.

The Implementation Notes of 00-09 describe a hotfix: adding ConfirmScreen inside launch_editor caused "TUI to drop to console and hang". The current code has moved ConfirmScreen to add_message_handler, but the symptom matches that exact description. This suggests the root cause may be in the suspend/resume mechanics itself, not the ConfirmScreen.

### Environmental Triggers
- Requires a real TTY (not headless CI environment).
- Only occurs with CLI editors (vim, nvim, nano, etc.).
- Does NOT occur with GUI editors (code, cursor) which use the Popen + ConfirmScreen path.
- Does NOT occur in the Console ask loop (which uses subprocess.run without TUI suspend).

### Ruled Out
- Caller-specific behaviors (handle_edit_action, add_message_handler) are not causing the issue; all paths converge on launch_editor().
- The precedent preview_readonly() uses the same app.suspend() pattern (without _flush_stdin()) and works correctly.
- GUI editor path (Popen + ConfirmScreen) works correctly.

## Diagnostic Analysis
### Causal Model
The `launch_editor()` function in `textual_plan_reviewer_editor.py` uses the following flow for CLI editors:
```
with app.suspend():
    await anyio.to_thread.run_sync(lambda: subprocess.run(editor_cmd + [temp_file]))
    _flush_stdin()
```
After the `with` block, it reads the temp file, strips escape sequences, splits on instruction marker, and returns the content. The caller then optionally shows a ConfirmScreen. The TUI should resume automatically when `app.suspend()` exits. The fact that it does not resume suggests either:
1. `app.suspend()` exits but does not restore the alternate screen (Textual bug or interactive state).
2. An unhandled exception in the `with` block propagates and causes the app to exit prematurely (but user reports hang, not crash).
3. `_flush_stdin()` (specifically `termios.tcflush(sys.stdin, termios.TCIFLUSH)`) inside the suspend block interferes with the terminal state that Textual needs to restore.

### Discrepancies
- `preview_readonly()` uses `app.suspend()` with `anyio.to_thread.run_sync` without `_flush_stdin()` and works correctly - this narrows the discrepancy to `_flush_stdin()` or the specific subprocess.run vs run_command call. (Resolved: `_flush_stdin()` calls `termios.tcflush()` which flushes terminal response data that Textual's `resume_application_mode()` needs to read. `preview_readonly()` does NOT call flush, so it works correctly.)
- The user reports hang (no crash), which contradicts an exception propagation hypothesis. (Resolved: The hang is caused by Textual's `resume_application_mode()` waiting indefinitely for terminal responses that were flushed by `tcflush`. No crash — the event loop hangs in an I/O wait.)
- The hotfix description matches the symptom exactly, but the hotfix was supposed to fix it by moving ConfirmScreen out of launch_editor. The symptom persists, so the hotfix addressed a different causation layer. (Resolved: The hotfix moved ConfirmScreen out of launch_editor, fixing the screen-stack instability. But the underlying `_flush_stdin()` inside suspend remained, causing the same terminal-drop-and-hang symptom from a different mechanism.)
- User reports "Vim: Warning: Input is not from a terminal" when pressing `e`. (Resolved: This confirms vim does not receive a proper TTY handover inside `app.suspend()`, further supporting the terminal state interference hypothesis.)

### Investigation History
1. Context gathering: Read vertical slice 00-09, source files (textual_plan_reviewer_editor.py, textual_plan_reviewer_app.py, textual_plan_reviewer_previews.py), test file (test_tui_editor_suspend_resume.py), and git log. Identified three TUI editor fix commits. Noted that preview_readonly() works but launch_editor() with _flush_stdin() inside suspend does not.
2. MRE creation and execution: Created logical tests that verify suspend context entry/exit. Pytest failed due to test assertion bugs in MRE (incorrect assertions about delete_file calls), not code issues. Tests for the actual production code pass.
3. Regressing delta isolation: Examined diffs of three TUI editor fix commits (`aeeed302`, `f773f378`, `06836f63`). Identified that `_flush_stdin()` was moved from OUTSIDE to INSIDE the `app.suspend()` block in commit `06836f63`.
4. Supportive evidence research: Researched Textual's `app.suspend()` known issues (issues #6298, #6692). Found that suspend has known problems with terminal state restoration, and that `termios.tcflush(TCIFLUSH)` discards received-but-unread data that Textual's resume mechanism reads.
5. User alignment: Presented RCA to user. User confirmed all three diagnostic questions and added critical evidence: "Vim: Warning: Input is not from a terminal" — confirming terminal handover failure.
6. Shadow file creation: Created `spikes/debug/shadow_textual_plan_reviewer_editor.py` with `_flush_stdin()` moved outside the suspend block for verification.
7. Systemic audit: Confirmed no other `_flush_stdin()` calls exist inside suspend blocks. The only call site is in `launch_editor()`.

## Solution
### Root Cause
In `launch_editor()` (`textual_plan_reviewer_editor.py`, line 197), `_flush_stdin()` was called INSIDE the `with app.suspend():` context manager block. This function calls `termios.tcflush(sys.stdin, termios.TCIFLUSH)` which discards all received-but-unread data from the TTY input buffer.

When Textual exits the `app.suspend()` context, it calls `resume_application_mode()`, which sends terminal queries (escape sequences) and reads stdin for the responses. If `tcflush` has already flushed those responses (or other pending data), Textual's resume mechanism hangs indefinitely waiting for data that will never arrive. The alternate screen is never restored, leaving the user at the console with a hung process.

### Fix
Move `_flush_stdin()` from INSIDE the `with app.suspend():` block to IMMEDIATELY AFTER it. This ensures the flush happens after Textual has fully restored the alternate screen and completed its terminal state queries, so the flush cannot interfere with the resume mechanism.

```python
# Before (buggy):
with app.suspend():
    await anyio.to_thread.run_sync(lambda: subprocess.run(editor_cmd + [temp_file]))
    _flush_stdin()

# After (fixed):
with app.suspend():
    await anyio.to_thread.run_sync(lambda: subprocess.run(editor_cmd + [temp_file]))
_flush_stdin()
```

### Preventative Measures
This bug is a class of "terminal state interference during suspend context." To prevent similar issues:
1. **Never call `tcflush()` or manipulate stdin inside `app.suspend()`.** Any operation that reads, writes, or flushes stdin while Textual's suspend context is active risks interfering with the terminal state restoration.
2. **Document this rule** in the codebase for any future suspend/resume code.
3. **Audit for similar patterns:** All `_flush_stdin()` calls in the codebase should be verified to not occur inside Textual's suspend context. Systemic audit confirmed there is currently one call site, which this fix addresses.
