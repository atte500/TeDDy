# Task: 00-09 — TUI Editor Suspend/Resume for All Editor Paths

## Business Goal

Fix all 6 broken TUI editor code paths that fail to hand terminal control to CLI editors (vim, nvim, nano, etc.) because `launch_editor()` uses `subprocess.Popen()` without suspending Textual's alternate screen (`app.suspend()`). The Console flow was already fixed via `subprocess.run()` + escape sequence stripping + stdin flushing — replicate that pattern in the TUI's central `launch_editor()` function so every caller benefits automatically.

## Context

**Audit of all 7 TUI editor paths** (completed 2026-08-28):

| Path | Trigger | Handoff | Escape Strip | Stdin Flush | Status |
|------|---------|---------|-------------|-------------|--------|
| add_message | `m` key | ❌ Popen, no suspend | ❌ | ❌ | **BROKEN** |
| preview_edit | `e` on EDIT | ❌ Popen, no suspend | ❌ | ❌ | **BROKEN** |
| preview_create | `e` on CREATE | ❌ Popen, no suspend | ❌ | ❌ | **BROKEN** |
| preview_text_action | `e` on EXECUTE/RESEARCH | ❌ Popen, no suspend | ❌ | ❌ | **BROKEN** |
| view_details | `d` on executed | ❌ Popen, no suspend | ❌ | ❌ | **BROKEN** |
| view_plan | `v` key | ❌ Popen, no suspend | ❌ | ❌ | **BROKEN** |
| preview_readonly | `e` on READ | ✅ `app.suspend()` + `anyio.to_thread.run_sync()` | ✅ Terminal handles | ✅ Post-run | **WORKING** |

All broken paths flow through `launch_editor()` → `spawn_editor()` in `textual_plan_reviewer_editor.py`. The fix targets `launch_editor()` directly — a single change that fixes all 6 callers without modifying any of them individually.

**Console reference** (`console_interactor_ask_loop.py`):
- `_is_cli_editor()`: Classifies editor as CLI (`vim`, `nvim`, `nano`, etc.) or GUI (`code`, `cursor`, etc.) using basename comparison against a defined set.
- `_ESCAPE_SEQUENCE_RE`: Regex that strips ANSI SGR codes and OSC sequences (color palette resets, cursor positioning).
- `_flush_stdin()`: Drains terminal escape sequences from stdin after editor exit (POSIX `termios.tcflush` / Windows `msvcrt.kbhit` / graceful no-op fallback).
- CLI path: `subprocess.run(editor_cmd + [temp_path])` — blocking, returns harvested content directly.
- GUI path: `subprocess.Popen(editor_cmd + [temp_path])` — non-blocking, returns "" for harvest-on-Enter pattern.

**Root cause**: Textual's TUI uses the alternate screen buffer. `subprocess.Popen()` spawns the editor in the background while Textual retains control of the terminal. The editor never gets clean TTY access, resulting in garbled output and lost keystrokes. `app.suspend()` exists in the `ReviewerApp` instance and is already used correctly by `preview_readonly()`. We replicate that pattern in `launch_editor()`.

**Constraint:** Do NOT modify `preview_readonly()` — it already has correct suspend/resume. Do NOT modify any of the 6 preview/view handler callers. All changes are confined to `textual_plan_reviewer_editor.py`.

## Implementation Steps

### Step 1: Add CLI editor classification and escape-stripping constants
- **File:** [src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py](/src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py)
- **Change:** Add `import re` to existing imports. After the `logger = logging.getLogger(__name__)` line, add:

```python
# Regex to match ANSI SGR codes and OSC sequences (mirrors console_interactor_ask_loop.py)
_ESCAPE_SEQUENCE_RE = re.compile(
    r"\x1b\[[0-9;]*[a-zA-Z]"
    r"|\x1b\][^\x1b]*(?:\x1b\\|\x07)"
    r"|(?![\d;,])]10;(?:\d+;)?rgb:[\da-fA-F/]+(?::$|[a-zA-Z])?(?:\x1b\\|\x07)?"
)

# Set of known CLI (terminal) editors
_CLI_EDITORS: set[str] = {
    "vim", "nvim", "vi", "nano", "micro", "emacs", "pico", "helix", "hx", "kak",
}
```

### Step 2: Add helper functions for editor classification, stdin flush, and escape stripping
- **File:** [src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py](/src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py)
- **Change:** After `spawn_editor()` (around line 38), add these three functions:

```python
def _is_cli_editor(editor_cmd: Optional[list[str]]) -> bool:
    """Return True if the resolved editor command is a known terminal (CLI) editor."""
    if not editor_cmd:
        return False
    basename = os.path.basename(editor_cmd[0])
    return basename in _CLI_EDITORS


def _flush_stdin() -> None:
    """Flush stale escape sequences from the TTY input buffer after editor exit."""
    import sys

    try:
        import termios  # noqa: PLC0415
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except ImportError:
        try:
            import msvcrt  # noqa: PLC0415
            while msvcrt.kbhit():
                msvcrt.getwch()
        except ImportError:
            pass
    except Exception:
        pass


def _strip_escape_sequences(text: str) -> str:
    """Remove ANSI escape sequences and OSC control sequences from text."""
    return _ESCAPE_SEQUENCE_RE.sub("", text)
```

### Step 3: Modify `launch_editor()` to be editor-aware with suspend/resume for CLI editors
- **File:** [src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py](/src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py)
- **Change:** Replace the body of `launch_editor()` with editor-aware logic. The key structural change: after determining the editor command, classify it. For CLI editors: use `app.suspend()` + `anyio.to_thread.run_sync(subprocess.run)` — blocking, synchronous. After CLI editor exits: `_flush_stdin()`, read file, strip escape sequences, split at marker, return clean content (skip ConfirmScreen). For GUI editors: keep existing `spawn_editor()` + `_confirm_and_harvest()` pattern.

New `launch_editor()` body:

```python
async def launch_editor(
    app: "ReviewerApp",
    initial_content: str,
    suffix: str = ".txt",
    persistent_path: Optional[str] = None,
    skip_confirm: bool = False,
) -> Optional[str]:
    """Launches an external editor with editor-aware terminal handover.

    For CLI editors (vim, nvim, nano, etc.): uses app.suspend() + sync
    subprocess.run() with full terminal control, then strips escape sequences.
    For GUI editors (code, cursor, etc.): uses existing Popen + ConfirmScreen.
    """
    import subprocess  # nosec B404

    mock_out = os.environ.get("TEDDY_TEST_MOCK_EDITOR_OUTPUT")
    temp_file = persistent_path or app._system_env.create_temp_file(suffix=suffix)
    is_temp = persistent_path is None

    if mock_out is not None:
        handle_mock_editor(temp_file, mock_out)
        confirmed = (
            True
            if app.is_headless or skip_confirm
            else await app.push_screen_wait(ConfirmScreen())
        )
        return mock_out if confirmed else None

    try:
        if is_temp or (
            not os.path.exists(temp_file) or os.path.getsize(temp_file) == 0
        ):
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(str(initial_content))

        editor_cmd = app._console_tooling.find_editor()
        if not editor_cmd:
            return None

        if os.path.exists(temp_file):
            os.chmod(temp_file, 0o644)

        editor_name = (
            os.path.basename(editor_cmd[0])
            if isinstance(editor_cmd, list) and editor_cmd
            else "editor"
        )
        app.notify(f"Opening Editor: {editor_name}")

        # CLI editors: synchronous with suspend/resume for full terminal handover
        if _is_cli_editor(editor_cmd):
            logger.info("Opening Editor (sync): %s", editor_name)
            with app.suspend():
                await anyio.to_thread.run_sync(
                    lambda: subprocess.run(  # nosec B603
                        editor_cmd + [temp_file]
                    )
                )
            _flush_stdin()
            with open(temp_file, "r", encoding="utf-8") as f:
                content = f.read()
            content = _strip_escape_sequences(content)
            marker = app.INSTRUCTION_MARKER.strip()
            if marker in content:
                content = content.split(marker)[0].strip()
            if is_temp:
                app._system_env.delete_file(temp_file)
            return content if content else None

        # GUI editors: non-blocking Popen + ConfirmScreen (existing pattern)
        spawn_editor(editor_cmd, temp_file)
        return await _confirm_and_harvest(
            app, temp_file, initial_content, is_temp, skip_confirm=skip_confirm
        )
    except Exception as e:
        logger.debug("Failed to launch editor flow: %s", e)
        return None
    finally:
        if is_temp:
            app._system_env.delete_file(temp_file)
```

### Step 4: Write unit tests for the new editor-aware launch
- **File:** [tests/suites/unit/adapters/inbound/test_tui_editor_suspend_resume.py](/tests/suites/unit/adapters/inbound/test_tui_editor_suspend_resume.py) (new file)
- **Change:** Create tests covering:
  - Mock `app.suspend()` context manager and verify it's entered for CLI editors
  - Verify `subprocess.run()` is called (not Popen) for CLI editors
  - Verify `_flush_stdin()` is called after CLI editor exit
  - Verify `_strip_escape_sequences()` removes ANSI/OSC sequences from captured content
  - Verify GUI editors still use the old Popen+confirm path (regression guard)
  - Verify `preview_readonly()` is not affected (it has its own suspend pattern)
  - Verify `add_message_handler()` still stores harvested content in `_user_message_cache`
  - Verify all 6 callers still work (they call `launch_editor()` which delegates to appropriate path)

### Step 5: Run full test suite to verify no regressions
- **Change:** Run `uv run pytest -x` to verify all existing tests pass with the modified `launch_editor()`. Pay special attention to the following files that mock `launch_editor` or depend on `textual_plan_reviewer_editor`:
  - `test_tui_content_harvest.py`
  - `test_view_plan_regression.py`
  - `test_reviewer_app_core.py`
  - Any test patching `textual_plan_reviewer_editor.launch_editor`

If existing tests break because they relied on specific behavior of the old `Popen` path, update mocks to correspond to the new flow (e.g., mock `app.suspend()` context manager returns a no-op context manager).

## Verification

1. Press `m` in the TUI — vim opens with full terminal control, content is captured cleanly
2. Press `e` on an EDIT action — vim opens and edits are captured
3. Press `e` on a CREATE action — vim opens and content edits are captured
4. Press `e` on an EXECUTE/RESEARCH action — vim opens and command edits are captured
5. Press `v` to view the full plan — vim opens read-only, closes cleanly
6. Press `d` on an executed action — vim opens with log content, closes cleanly
7. Press `e` on a READ action — `preview_readonly()` still works (already correct)
8. GUI editors (code, cursor) still launch in background with ConfirmScreen popup
9. No terminal escape sequence pollution after any editor invocation
10. Full test suite passes: `uv run pytest -x`
11. No regressions in console ask loop editor paths (CLI and GUI)
