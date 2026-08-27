# Slice: Editor Subsystem Overhaul — Restore Background+Harvest Pattern

- **Status:** In Progress
- **Milestone:** N/A (ad-hoc quality fix)
- **Prototype:** N/A (prototype files from original scoping were not persisted — logic established by v0.1.13 codebase)
- **Component Docs:** [console_interactor.md](/docs/architecture/adapters/outbound/console_interactor.md), [system_environment_adapter.md](/docs/architecture/adapters/outbound/system_environment_adapter.md)
- **Scope Slug:** `editor-subsystem-overhaul`

## Business Goal

Eliminate the 5 reported editor issues (vim warning, backspace wonkiness, slow launch, missing opening log, GUI editors not captured) in one coordinated fix that restores the proven background+harvest-on-Enter pattern from v0.1.13 while preserving all hardening from subsequent fixes (escape sequence stripping, stdin flushing, marker splitting). Add two UX improvements: persistent temp file across multiple opens (until harvest), and TUI editor notification + s-key harvest.

## Scenarios

> As a user, I want to open vim from the ask loop and have it function as a proper interactive editor without warnings or corrupt terminal behavior.

```gherkin
Given I am in the ask loop
When I type "e" to open the editor
Then the editor subprocess inherits the real TTY via sys.stdin/stdout/stderr
And I see the log message "Opening Editor: vim" before the editor appears
And vim does NOT show "Warning: Input is not from a terminal"
And backspace and other special keys behave correctly
And there is no startup delay from failed TTY negotiation
```

> As a user, I want to open a GUI editor (e.g., VS Code) and have my edits captured when I press Enter, without waiting for the editor to close.

```gherkin
Given I am in the ask loop
When I type "e" to open the editor
And the editor is a GUI editor (VS Code, TextEdit, gedit)
Then the editor launches in the background
And the prompt changes to "Editor opened. Terminal reply or [Enter] to confirm editor ›"
When I finish editing and press Enter
Then the file content is harvested from the temp file
And the harvested content is returned as my response
```

> As a user, I want the system to log which editor is being opened before the launch.

```gherkin
Given I am in the ask loop
When I type "e" to open the editor
Then a log message "Opening Editor: [editor name]" is emitted BEFORE the editor subprocess starts
```

> As a user, I want my previous edits to be preserved when I re-open the editor multiple times in the same cycle, until I harvest the content with Enter.

```gherkin
Given I am in the ask loop
When I type "e" to open the editor the first time
And I type some text and close the editor
And I type "e" again before pressing Enter
Then the editor reopens with my previous text preserved
And I can continue editing where I left off
When I press Enter to harvest
Then the final content is returned
And the temp file is cleaned up
```

> As a user in the TUI, I want to see a quick "Opening Editor: [name]" notification instead of a confirmation popup.

```gherkin
Given I am in the TUI plan reviewer
When I press "m" to add a message
Then a non-blocking notification "Opening Editor: [name]" is displayed for ~4 seconds
And the editor launches in the background
And I see no "Confirm editing done?" popup
When I press "s" to submit the plan
Then the message content is harvested from the persistent temp file
```

## Edge Cases

- **No TTY (CI/pipe):** If stdin is not a TTY, the background editor launch must use DEVNULL stdin/out/err and skip TTY-dependent operations. The ask loop should indicate "Editor not available in non-TTY mode" or similar.
- **Editor not found:** If `find_editor()` returns None, display error message and return to ask loop without launching.
- **Escape sequences injected during editor runtime:** The `_flush_stdin()` and `_strip_escape_sequences()` mechanisms must be preserved — flush after editor spawn, strip on file harvest.
- **Empty file after editor:** If the user deletes all content and closes the editor, the file will be empty. The harvest returns empty string, triggering the "Press [Enter] again to confirm empty response" path — same as current behavior.
- **Editor crash/hang:** The background editor process is fire-and-forget via `subprocess.Popen`. If it crashes, the temp file retains whatever was written. If it hangs, the user can still press Enter to harvest whatever content exists, or use the terminal reply feature.
- **Persistent file lifecycle:** The temp file is created on first editor open, reused on subsequent opens while `_active_editor_path` is set, and cleaned up when the user presses Enter to harvest. It is NOT kept for the entire session.
- **MacOS with "open -a" default editor:** The `find_editor()` method should handle the case where the editor command contains flags (e.g., `open -a TextEdit /tmp/file`). Currently it only does `which(parts[0])` — open is found but flags may not work with subprocess. For now, this edge case is deferred.

## Key Unknowns

- [x] [Technical] Does the background editor path correctly handle both terminal and GUI editors? — Confirmed by v0.1.13 code and user verification.
- [x] [Technical] Are there other consumers of ConsoleAskLoop that would be affected? — Audit shows only ConsoleInteractorAdapter instantiates it.
- [x] [Technical] Is there any other code path using subprocess.run with DEVNULL stdin for interactive tools? — Audit confirmed only the editor path in `system_environment_adapter.py`.
- [x] [Technical] Does the TUI editor need unification? — Confirmed: TUI already uses background+harvest correctly, only needs notification and s-key harvest.

## Implementation Plan

### Approach: Restore background+harvest + persistent file + TUI notification + s-key harvest

The fix targets two files: `console_interactor_ask_loop.py` and `textual_plan_reviewer_editor.py`.

**Console Ask Loop (`console_interactor_ask_loop.py`):**

1. **Restore `_launch_editor_background()`**: Use `subprocess.Popen` with `stdin=sys.stdin`, `stdout=sys.stdout`, `stderr=sys.stderr` (TTY inheritance). Store `_active_editor_path`. **Persistent file:** on subsequent opens while `_active_editor_path` is set, read existing content, strip marker+prompt, write that as initial content (so previous edits are preserved). Remove VIMINIT suppression.
2. **Add logging**: `log.info("Opening Editor: %s", editor_name)` BEFORE the spawn.
3. **Restore harvest in `_handle_empty_input()`**: When `_active_editor_path` is set, read file, strip escape sequences, return content, call `cleanup()` (delete temp file, reset `_active_editor_path`).
4. **Remove `_open_editor_blocking()`**: No longer needed.
5. **Preserve**: Keep `_ESCAPE_SEQUENCE_RE` + `_strip_escape_sequences()`, `_flush_stdin()`, marker splitting, `_is_tty()` guard.
6. **Adjust prompt text**: "Editor opened. Terminal reply or [Enter] to confirm editor ›" when `_active_editor_path` is set.

**TUI Editor (`textual_plan_reviewer_editor.py`):**

1. **Add notification**: `app.notify(f"Opening Editor: {editor_name}")` in `launch_editor()`.
2. **Replace ConfirmScreen**: Remove the `confirm` check in `_confirm_and_harvest()` — harvest is triggered by the plan submit (`s`) key, not a popup confirmation.
3. **Persistent temp file**: Store `persistent_path` in the action (e.g., `action.pending_message_file`) and reuse across multiple 'm' opens.
4. **Harvest on submit**: When the plan is submitted with `s`, read the message from the persistent temp file set during `launch_editor()`.

### Dependencies
- No contract changes needed (no Ports change).
- No config changes needed.
- Console: `console_interactor_ask_loop.py`.
- TUI: `textual_plan_reviewer_editor.py`, potentially `textual_plan_reviewer_app.py` (s-key wiring).
- Tests: Update mocks in `test_console_ask_loop_escape_stripping.py`, `test_console_ask_loop_stdin_flush.py`.

## Deliverables

- [x] **Wiring (Console)** — Modify `ConsoleAskLoop.run()` and `_handle_empty_input()` to use `_launch_editor_background` instead of `_open_editor_blocking`. Add opening log. Update prompt text for active editor state.
- [ ] **Logic (Console)** — Implement `_launch_editor_background()` with `subprocess.Popen` + TTY inheritance + persistent file reuse. Implement harvest logic in `_handle_empty_input()` to read `_active_editor_path`, strip escape sequences, and return content. Remove `_open_editor_blocking()`.
- [ ] **Wiring (TUI)** — Replace ConfirmScreen with notification in `launch_editor()`. Wire s-key harvest in `textual_plan_reviewer_app.py` to read persistent temp file when submitting plan.
- [ ] **Logic (TUI)** — Implement persistent temp file storage in action. Store/retrieve `pending_message_file` across launches.
- [ ] **Migration** — Update `test_console_ask_loop_escape_stripping.py` to mock background path instead of blocking path. Update `test_console_ask_loop_stdin_flush.py` to verify flush timing in new flow.
- [ ] **Cleanup** — Remove `_open_editor_blocking()`, VIMINIT suppression, and `test_console_ask_loop_stdin_flush.py` if redundant with escape stripping tests.

## Implementation Notes

### Wiring (Console) — Deliverable 1

**Changes made:**
- Added `import logging` and `logger = logging.getLogger(__name__)` to `console_interactor_ask_loop.py`.
- Implemented `_launch_editor_background(self, prompt: str) -> str` as a Tracer Bullet method: logs the editor name via `logger.info("Opening Editor: %s", editor_name)` and returns the prompt string as trivial/hardcoded content.
- Updated `run()` to call `self._launch_editor_background(prompt)` instead of `self._open_editor_blocking(prompt)`.
- Updated `_handle_empty_input()` to call `self._launch_editor_background(prompt)` instead of `self._open_editor_blocking(prompt)`.
- Created new test file `test_console_ask_loop_editor_background.py` with one test verifying that typing 'e' calls `_launch_editor_background` and returns its content.
- Updated `test_console_ask_loop_escape_stripping.py`: replaced all `_open_editor_blocking` references with `_launch_editor_background` in mock patches.
- Updated `test_console_interactor.py`: replaced three editor-related tests to mock `_launch_editor_background` directly instead of the old `_open_editor_blocking`/`run_command` pattern.

**Key decisions:**
- The Wiring deliverable uses trivial return values (returns the prompt string) to prove the end-to-end path. The real background+harvest logic will be implemented in the Logic (Console) deliverable.
- `_open_editor_blocking()` is preserved for now — it will be removed in the Cleanup deliverable.
- A new dedicated test file was created for the background editor flow to avoid modifying the escape stripping tests during the Wiring phase.

**Frictions encountered:**
- `git grep --include` flag is not supported on the installed git version — use direct path arguments instead.
- Python script-based multiline replacement for test functions was fragile due to nested functions (`def mock_run_command`) causing incorrect function boundary detection. Fix required a second pass to remove stale residual code.

### Tracer Bullet Logic
The Wiring deliverable's `_launch_editor_background` simply returns the prompt string:
```python
return prompt if prompt else ""
```
This will be replaced by real `subprocess.Popen` + TTY inheritance + persistent file reuse in the Logic deliverable.

## Verification

- [ ] All 5 issue symptoms no longer reproduce.
- [ ] MRE `26-editor-devnull-stdin-mre.py` shows TTY detection difference (informational).
- [ ] Regression tests for escape stripping and stdin flush pass with updated mocks.
- [ ] Full test suite passes.
- [ ] User confirms "Opening Editor: vim" log appears before editor launch.
- [ ] User confirms vim works without terminal warning.
- [ ] User confirms GUI editors are captured when pressing Enter.
- [ ] User confirms re-opening editor preserves previous text (persistent file).
- [ ] User confirms TUI shows brief "Opening Editor: [name]" notification instead of confirm popup.
- [ ] User confirms TUI message content is harvested on plan submit (s key).
