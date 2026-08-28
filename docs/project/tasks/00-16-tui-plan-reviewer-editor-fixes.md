# Task: TUI Plan Reviewer Editor Fixes

## Business Goal

Fix three issues with the TUI plan reviewer's editor integration: remove unnecessary save confirmation when adding messages, make the diff viewer work with CLI editors (vim/nvim) via a translation table, and remove the editor fallback chain with proper notification when no editor is configured.

## Context

The Textual TUI plan reviewer has three editor-related issues that have been analyzed and approved:

**Issue 4 (ask_loop 'e' key — no editor configured):** The console-based ask_loop (`ConsoleAskLoop._launch_editor_background`) currently uses `self._tooling.find_editor() or ["vim"]`, which silently falls back to vim if no editor is configured. When no editor is found, the ask_loop should print a notification to the user (similar to the TUI's `app.notify`) and return to the prompt without opening an editor.

**Issue 1 ('m' key — save confirmation):** When pressing `m` to add a message, the GUI editor path (`spawn_editor`) uses `_confirm_and_harvest` which pushes a `ConfirmScreen`. The user wants no confirmation — just a notification that the editor is opening, and content is harvested on final submission (pressing `s`). The CLI editor path (vim/nvim) already skips confirmation correctly.

**Issue 2 ('e' EDIT action — CLI editor diff viewer):** `preview_edit_diff_viewer` relies on `get_diff_viewer_command()` which currently only returns a command for VS Code. For CLI editors, the flow breaks. Research (covering vim, nvim, code, cursor, codium, zed, idea, subl, emacs, nano, helix, kak, gedit, kate, notepad++) confirms that `-d` is NOT universal — only vim/nvim support it. The solution is a translation table mapping editor basenames to their diff flags. For editors with diff support, the function returns the command; for others, it returns `None` (falling back to opening proposed content directly).

**Issue 3 (editor fallback chain — deprecation):** `find_editor()` falls back to hardcoded `code`/`nano` if no editor is configured or available. The user wants the fallback removed — only use config or env var. If no editor is found, `launch_editor` should notify the user with a clear message.

### Files to Modify

- **[textual_plan_reviewer_previews.py](/src/teddy_executor/adapters/inbound/textual_plan_reviewer_previews.py):** `add_message_handler` — passes `skip_confirm=True`, removes post-editor ConfirmScreen block.
- **[textual_plan_reviewer_editor.py](/src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py):** `launch_editor` — adds notification when `find_editor()` returns `None`. `preview_edit_diff_viewer` — adds CLI editor suspend/harvest path.
- **[console_tooling.py](/src/teddy_executor/adapters/outbound/console_tooling.py):** `ConsoleToolingHelper` — adds `_DIFF_FLAGS` translation table, updates `get_diff_viewer_command()`, removes fallback chain from `find_editor()`, removes VS Code special-casing from `_resolve_editor_cmd()`.
- **[test_console_tooling_editor.py](/tests/suites/unit/adapters/outbound/test_console_tooling_editor.py):** Updates tests for new `get_diff_viewer_command` behavior.
- **[test_tui_editor_suspend_resume.py](/tests/suites/unit/adapters/inbound/test_tui_editor_suspend_resume.py):** Adds tests for `preview_edit_diff_viewer` CLI editor suspend path.
- **[test_reviewer_app_core.py](/tests/suites/unit/adapters/inbound/test_reviewer_app_core.py):** Updates existing tests to match new notification/add_message_handler behavior.
- **[console_interactor_ask_loop.py](/src/teddy_executor/adapters/outbound/console_interactor_ask_loop.py):** `_launch_editor_background` — replace silent fallback `or ["vim"]` with notification when no editor is configured.
- **[test_console_ask_loop_editor_background.py](/tests/suites/unit/adapters/outbound/test_console_ask_loop_editor_background.py):** Add tests for no-editor notification behavior.

### Assumptions & Agreements

- `TEDDY_DIFF_TOOL` env var remains as the explicit override — translation table only applies when it's not set.
- For CLI editors without diff support (nano, helix, emacs, etc.), `get_diff_viewer_command()` returns `None`, and `preview_edit` falls through to `launch_editor` with proposed content — same behavior as today.
- Notification text for missing editor: "No editor configured. Please configure one in .teddy/config.yaml"
- All existing tests must continue to pass; update tests that relied on the fallback chain or old code-specific hardcoding.

## Implementation Steps

### Step 1: Add notification when no editor configured

- **File:** [src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py](/src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py)
- **Change:** In `launch_editor()`, after the line `editor_cmd = app._console_tooling.find_editor()`, modify the `if not editor_cmd` block to call `app.notify(...)` before `return None`:

```python
editor_cmd = app._console_tooling.find_editor()
if not editor_cmd:
    app.notify(
        "No editor configured. Please configure one in .teddy/config.yaml"
    )
    return None
```

### Step 2: Add diff flag translation table to ConsoleToolingHelper

- **File:** [src/teddy_executor/adapters/outbound/console_tooling.py](/src/teddy_executor/adapters/outbound/console_tooling.py)
- **Change:** Add a class-level `_DIFF_FLAGS` dictionary to `ConsoleToolingHelper` and update `get_diff_viewer_command()` to use the configured editor with the translation table instead of the hardcoded `code` path.

```python
_DIFF_FLAGS: dict[str, list[str]] = {
    "vim": ["-d"],
    "vi": ["-d"],
    "nvim": ["-d"],
    "code": ["--diff"],
    "cursor": ["--diff"],
    "codium": ["--diff"],
    "zed": ["--diff"],
    "idea": ["diff"],
}
```

Replace the entire `get_diff_viewer_command()` method:

```python
def get_diff_viewer_command(self) -> Optional[List[str]]:
    custom_tool_str = self._system_env.get_env("TEDDY_DIFF_TOOL")
    if custom_tool_str:
        custom_tool_parts = shlex.split(custom_tool_str)
        tool_name = custom_tool_parts[0]
        if tool_path := self._system_env.which(tool_name):
            custom_tool_parts[0] = tool_path
            return custom_tool_parts
        return None

    # Use configured editor with translation table
    editor_cmd = self.find_editor()
    if not editor_cmd:
        return None
    basename = os.path.basename(editor_cmd[0]).lower()
    if flags := self._DIFF_FLAGS.get(basename):
        return editor_cmd + flags
    return None
```

Add `import os` to the top of the file if not already present.

### Step 3: Remove editor fallback chain from find_editor()

- **File:** [src/teddy_executor/adapters/outbound/console_tooling.py](/src/teddy_executor/adapters/outbound/console_tooling.py)
- **Change:** Remove the entire "Discovery Fallback" block (step 3) from `find_editor()`. The method should only check config and env vars, then return `None` if neither is set.

```python
def find_editor(self) -> Optional[List[str]]:
    # 1. Check Config
    if cmd := self._resolve_editor_cmd(self._config_service.get_setting("editor")):
        return cmd

    # 2. Check Env
    env_editor = self._system_env.get_env("VISUAL") or self._system_env.get_env(
        "EDITOR"
    )
    if cmd := self._resolve_editor_cmd(env_editor):
        return cmd

    return None
```

### Step 4: Remove VS Code special-casing from _resolve_editor_cmd()

- **File:** [src/teddy_executor/adapters/outbound/console_tooling.py](/src/teddy_executor/adapters/outbound/console_tooling.py)
- **Change:** Remove the block that appends `-r` and `--wait` for VS Code from `_resolve_editor_cmd()`. The method should resolve the path and return the command as-is:

```python
def _resolve_editor_cmd(self, editor_str: Optional[str]) -> Optional[List[str]]:
    if not editor_str:
        return None
    parts = shlex.split(editor_str)
    if tool_path := self._system_env.which(parts[0]):
        parts[0] = tool_path
        return parts
    return None
```

### Step 5: Handle CLI diff editors with suspend in preview_edit_diff_viewer

- **File:** [src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py](/src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py)
- **Change:** Update `preview_edit_diff_viewer()` to detect if the diff viewer is a CLI editor and use suspend + subprocess instead of background + ConfirmScreen. Import `_restore_foreground_process_group` and `_restore_terminal_cooked_mode` (they're already defined in this file). For CLI editors, auto-harvest after suspend (no confirm needed). For GUI editors, keep the existing flow.

Replace the `preview_edit_diff_viewer` function body. The key change is to add a check after `prepare_after_file`:

```python
if _is_cli_editor(diff_viewer):
    # CLI editor diff: suspend TUI, run in foreground, auto-harvest
    import subprocess  # noqa: PLC0415
    try:
        with app.suspend():
            subprocess.run(diff_viewer + [str(before), str(p_file)])
        _restore_foreground_process_group()
        _restore_terminal_cooked_mode()
        # Auto-harvest: read the edited after file
        harvest_edit_diff(action, p_file, original, proposed)
        app._system_env.delete_file(before)
        return True
    except Exception as e:
        logger.debug("Failed to run CLI diff viewer: %s", e)
        app._system_env.delete_file(before)
        return False
```

Keep the existing GUI code path unchanged after this block (else the existing `if p_file and isinstance(...)` block runs the GUI flow).

### Step 6: Pass skip_confirm and remove post-editor confirm in add_message_handler

- **File:** [src/teddy_executor/adapters/inbound/textual_plan_reviewer_previews.py](/src/teddy_executor/adapters/inbound/textual_plan_reviewer_previews.py)
- **Change:** In `add_message_handler()`, pass `skip_confirm=True` to `launch_editor()` and remove the block that shows `ConfirmScreen` after `launch_editor` returns.

Replace the call to `launch_editor` and the post-editor block:

```python
new_message = await launch_editor(
    app,
    current_message,
    suffix=".md",
    persistent_path=app._pending_message_file,
    skip_confirm=True,
)
if new_message is not None and new_message != current_message:
    app._user_message_cache = new_message
```

Note: Remove the `from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import ConfirmScreen` import from the top of the file if it's no longer used elsewhere.

### Step 7: Update unit tests for console_tooling

- **File:** [tests/suites/unit/adapters/outbound/test_console_tooling_editor.py](/tests/suites/unit/adapters/outbound/test_console_tooling_editor.py)
- **Change:** Update tests that tested the old fallback chain behavior and the old code-specific `get_diff_viewer_command`. Add tests for:
  - `get_diff_viewer_command` returns correct command for known editors (vim, code)
  - `get_diff_viewer_command` returns `None` for unknown editors (nano)
  - `get_diff_viewer_command` respects `TEDDY_DIFF_TOOL` env var override
  - `find_editor` returns `None` when no config or env var is set
  - `find_editor` does NOT fall back to code/nano

### Step 8: Update TUI editor tests for CLI diff viewer suspend

- **File:** [tests/suites/unit/adapters/inbound/test_tui_editor_suspend_resume.py](/tests/suites/unit/adapters/inbound/test_tui_editor_suspend_resume.py)
- **Change:** Add tests for `preview_edit_diff_viewer` CLI editor suspend path:
  - CLI editor diff viewer triggers `app.suspend()` and `subprocess.run()`
  - GUI editor diff viewer does NOT trigger suspend
  - Auto-harvest after CLI diff viewer returns modified content
  - Before file is deleted after CLI diff viewer completes

### Step 9: Update existing reviewer app tests

- **File:** [tests/suites/unit/adapters/inbound/test_reviewer_app_core.py](/tests/suites/unit/adapters/inbound/test_reviewer_app_core.py)
- **Change:** Update any tests for `add_message_handler` that relied on the old confirm behavior. Ensure tests pass with the new `skip_confirm=True` flow.

### Step 10: Add "No editor configured" notification to ask_loop

- **File:** [src/teddy_executor/adapters/outbound/console_interactor_ask_loop.py](/src/teddy_executor/adapters/outbound/console_interactor_ask_loop.py)
- **Change:** In `_launch_editor_background()`, replace the silent fallback `self._tooling.find_editor() or ["vim"]` with a check that logs a notification when no editor is found. If `find_editor()` returns `None`, log a notification and return an empty string (continuing the interactive loop without opening an editor).

Replace the line:

```python
editor_cmd = self._tooling.find_editor() or ["vim"]
```

with:

```python
editor_cmd = self._tooling.find_editor()
if not editor_cmd:
    logger.info(
        "No editor configured. Please configure one in .teddy/config.yaml"
    )
    return ""
```

- **File:** [tests/suites/unit/adapters/outbound/test_console_ask_loop_editor_background.py](/tests/suites/unit/adapters/outbound/test_console_ask_loop_editor_background.py)
- **Change:** Add a new test class or test method that verifies:
  - When `find_editor()` returns `None`, `_launch_editor_background` returns `""` (empty string) and does NOT invoke `subprocess.run` or `subprocess.Popen`.
  - A log message with "No editor configured" is generated (use `caplog` or verify `logger.info` was called).
  - The fallback `or ["vim"]` is no longer present (structural test: the method does not use `or ["vim"]` anywhere).

## Verification

1. Run the full test suite: `uv run pytest` — all existing tests must pass.
2. Run unit tests for affected modules:
   - `uv run pytest tests/suites/unit/adapters/outbound/test_console_tooling_editor.py -v`
   - `uv run pytest tests/suites/unit/adapters/inbound/test_tui_editor_suspend_resume.py -v`
   - `uv run pytest tests/suites/unit/adapters/inbound/test_reviewer_app_core.py -v`
3. Manually verify in TUI:
   - Press `m` — notification "Opening Editor: name" appears, editor opens, no confirm prompt after closing.
   - Press `e` on an EDIT action with vim as editor — `vim -d` opens showing original vs proposed, user can edit right side, save/quit, changes are harvested.
   - Press `e` on an EDIT action with nano as editor — proposed content opens directly in nano (no diff), user edits and saves.
   - Remove editor config and set `EDITOR` env var to empty — pressing `e` or `m` shows notification "No editor configured. Please configure one in .teddy/config.yaml".
4. Verify no editor fallback: when no config and no env var, `find_editor()` returns `None` (previously it would fall back to `code` or `nano`).
5. Verify `get_diff_viewer_command` returns correct commands for known editors (e.g., `["vim", "-d"]`, `["code", "--diff"]`).
6. Verify `TEDDY_DIFF_TOOL` env var still overrides the translation table.
7. Run ask_loop tests: `uv run pytest tests/suites/unit/adapters/outbound/test_console_ask_loop_editor_background.py -v`. Verify:
   - When `find_editor()` returns `None`, `_launch_editor_background` returns `""` and logs a notification.
   - The old fallback `or ["vim"]` is no longer present in the code.
   - `subprocess.run` / `subprocess.Popen` are NOT called when no editor is configured.
