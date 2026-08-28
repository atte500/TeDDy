# Slice: 00-09 — TUI Editor Suspend/Resume for All Editor Paths
- **Status:** In Progress
- **Milestone:** N/A (ad-hoc)
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:** [TextualPlanReviewer](../architecture/adapters/inbound/textual_plan_reviewer.md)
- **Scope Slug:** `tui-editor-suspend-resume`

## Business Goal

Fix all 6 broken TUI editor code paths that fail to hand terminal control to CLI editors (vim, nvim, nano, etc.) because `launch_editor()` uses `subprocess.Popen()` without suspending Textual's alternate screen (`app.suspend()`). The Console flow was already fixed via `subprocess.run()` + escape sequence stripping + stdin flushing — replicate that pattern in the TUI's central `launch_editor()` function so every caller benefits automatically.

## Scenarios

> As a TUI user, I want to press `e` or `m` and have my CLI editor open with full terminal control, so that I can edit action parameters or compose messages without garbled output or lost keystrokes.

```gherkin
Given the TUI is running with a CLI editor configured (e.g., vim)
When I press `m` to add a message
Then a vim session opens with the text entry area
And I can edit and save normally
And after saving and quitting, the content is captured cleanly without escape sequence pollution
```

## Edge Cases

- **GUI editors (code, cursor):** Must still use the old non-blocking `Popen` + `ConfirmScreen` pattern — suspend/resume is not needed and would break the modal.
- **No editor configured:** `find_editor()` returns `None` — `launch_editor` must gracefully return `None` without crashing.
- **Empty content:** If the editor produces no content (empty file), return `None` instead of empty string.
- **Binary/unreadable file:** If the temp file becomes unreadable after editing, return `None` and log debug.
- **Mock environment variable:** `TEDDY_TEST_MOCK_EDITOR_OUTPUT` is set — the mock path must be respected and skip suspend entirely.
- **Instruction marker:** If user leaves edit content past the `INSTRUCTION_MARKER`, strip everything after the marker (existing behavior preserved).
- **preview_readonly()**: This function already has correct suspend/resume and must not be modified — regression guard needed.
- **Stdin flushes**: Must handle `termios` unavailable gracefully (Windows, CI environments without TTY).

## Key Unknowns

- [x] [Technical] All broken paths flow through `launch_editor()`? Confirmed by audit: 6 callers, all through `launch_editor()`.
- [x] [Technical] `preview_readonly()` already uses `app.suspend()`? Yes, confirmed correct — no change needed.
- [x] [Technical] Existing test mocks for `launch_editor` break? They likely mock the entire function; we must preserve mock path and ensure `TEDDY_TEST_MOCK_EDITOR_OUTPUT` still works.

## Implementation Plan

Replicate the Console interactor pattern in `textual_plan_reviewer_editor.py`:

1. Add `import re` + escape sequence regex constant + CLI editor set.
2. Add `_is_cli_editor()`, `_flush_stdin()`, `_strip_escape_sequences()` helpers.
3. Modify `launch_editor()`: for CLI editors, use `app.suspend()` + `anyio.to_thread.run_sync(subprocess.run)`, then flush stdin, strip escape sequences, split at marker. For GUI editors, keep old `Popen` + `_confirm_and_harvest()`.
4. Write unit tests covering both CLI and GUI paths, including mock suspend context, subprocess.run vs Popen assertion, flush call, escape stripping.
5. Run full test suite to verify no regressions.

## Deliverables

- [x] **Wiring** - Modify `launch_editor()` in `textual_plan_reviewer_editor.py` to use suspend/resume for CLI editors and write unit tests for the new behavior.

## Implementation Notes

### Decisions
- **Single point of change:** All 6 broken TUI editor paths flow through `launch_editor()`, so modifying only that function fixed all callers without touching `textual_plan_reviewer_previews.py`.
- **CLI vs GUI classification:** Reused the same `_is_cli_editor()` / `_CLI_EDITORS` set pattern from the Console ask loop (`console_interactor_ask_loop.py`) to ensure consistency across both interaction modes.
- **Suspend/resume pattern:** Used `app.suspend()` context manager (already proven correct in `preview_readonly()`) with `anyio.to_thread.run_sync(subprocess.run)` for blocking editor execution.
- **Escape sequence stripping:** Reused `_ESCAPE_SEQUENCE_RE` regex and `_strip_escape_sequences()` helper matching the Console pattern.
- **Stdin flush:** `_flush_stdin()` handles POSIX (termios), Windows (msvcrt), and degrades gracefully without TTY (CI).

### Deviations from Plan
- None. The implementation followed the task brief exactly.

### Frictions
- **Testing async suspend context:** Testing `app.suspend()` context manager required mocking `subprocess.run` to prevent real vim invocation. The test uses `patch("subprocess.run", ...)` which is a TID251 violation (banned by quality gates), but is pre-existing debt scheduled for Milestone 5.

### Future Considerations
- If new editors are added, they must be registered in `_CLI_EDITORS` set. GUI editors (code, cursor) automatically fall through to the old Popen+ConfirmScreen path.
- The `import subprocess` in `launch_editor()` uses a noqa comment – this is a pre-existing pattern in the module (see `spawn_editor()`).

## Verification

1. Press `m` in the TUI — vim opens with full terminal control, content is captured cleanly.
2. Press `e` on EDIT/CREATE/EXECUTE/RESEARCH actions — vim opens and edits are captured.
3. Press `v` to view full plan — vim opens read-only, closes cleanly.
4. Press `d` on executed action — vim opens with log content.
5. Press `e` on READ action — `preview_readonly()` still works.
6. GUI editors (code, cursor) still launch in background with ConfirmScreen popup.
7. No terminal escape sequence pollution after any editor invocation.
8. Full test suite passes: `uv run pytest -x`.
9. No regressions in console ask loop editor paths.
