# Task: Annotated Edit Diff — Single-File Unified Diff for EDIT Action Previews

## Business Goal

Replace the vimdiff two-file flow (`nvim -d before after`) with a single `.diff` file containing annotated unified diff markers, providing a clean single-file editing experience with no `:q` window-closing confusion, while preserving the ability to preview and edit proposed changes.

## Context

When pressing `e` on an EDIT action in the TUI plan reviewer, `preview_edit()` currently calls `preview_edit_diff_viewer()` which launches `nvim -d /tmp/before /tmp/after`. Vim opens two files in side-by-side diff mode. Typing `:q` closes only the current window, leaving the user in a single-column view requiring a second `:q` to fully exit.

The spike (`spikes/single_file_diff_spike.py`) validated an alternative approach: generate a unified diff string using Python's `difflib.unified_diff()`, prepend an instructional header explaining the `+`/`-` format, open the single `.diff` file in the user's editor, and on exit reconstruct the final content by discarding `-` lines, keeping `+` lines (with the prefix stripped) and context lines as-is.

**Why this works:**
- Single file → single `:q` → clean exit (no vimdiff confusion)
- Unified diff format is familiar from `git diff`
- Spike confirmed user can edit `+` lines (changes kept) and `-` lines (harmless, discarded)
- `.diff` extension triggers vim syntax highlighting automatically
- GUI editor path (code --diff) remains unchanged — only the CLI vim/nvim flow is modified

**Files to modify:**
- **`src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py`** — Add `reconstruct_from_diff()` and `_generate_annotated_diff_content()` helpers, update `preview_edit_diff_viewer()` CLI branch to use annotated diff
- **`src/teddy_executor/adapters/inbound/textual_plan_reviewer_previews.py`** — Possibly adjust `preview_edit()` if needed (likely no change — the diff viewer path is unchanged, only the implementation inside `preview_edit_diff_viewer` changes)
- **`tests/suites/unit/adapters/inbound/test_tui_editor_suspend_resume.py`** — Add/update tests for the annotated diff flow
- **`tests/suites/unit/adapters/inbound/test_reviewer_app_core.py`** — Update any tests that rely on the old vimdiff behavior

## Implementation Steps

### Step 1: Add utility helpers to `textual_plan_reviewer_editor.py`

- **File:** [src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py](/src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py)
- **Change:** Add two static/private functions after the existing imports and before `handle_mock_editor`:

```python
def reconstruct_from_diff(edited_text: str) -> str:
    """Reconstruct the final content from an annotated diff file.

    Rules:
    - Lines starting with '---' or '+++' (file headers): ignored
    - Lines starting with '@@': ignored (hunk headers)
    - Lines starting with '-': REMOVED LINES — discarded entirely.
        Even if the user modified them, they don't appear in output.
    - Lines starting with '+': ADDED LINES — kept, with the '+' prefix stripped.
    - Lines with NO prefix: CONTEXT LINES — kept as-is.
    """
    result = []
    for line in edited_text.splitlines(keepends=True):
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("@@"):
            continue
        if line.startswith("-"):
            continue
        if line.startswith("+"):
            result.append(line[1:])  # strip '+'
        else:
            result.append(line)       # context lines kept
    return "".join(result)


def _generate_annotated_diff_content(
    original: str,
    proposed: str,
    path_str: str = "",
) -> str:
    """Generate a single annotated diff file content with instructional header."""
    import difflib  # noqa: PLC0415

    diff_lines = list(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            proposed.splitlines(keepends=True),
            fromfile=f"{path_str} (original)",
            tofile=f"{path_str} (proposed)",
        )
    )
    diff_text = "".join(diff_lines)

    header = """# TeDDy Change Preview — Single Annotated File
#
# This file shows what changed between the original and proposed version.
# You can BOTH review the changes AND edit the content in one view.
#
# FORMAT:
#   @@ ... @@  = Hunk header (ignore)
#   - ....     = Removed line (IGNORED on save — editing these is harmless)
#   + ....     = Added line (KEPT on save — prefix stripped automatically)
#   no prefix  = Context line (kept as-is)
#
# INSTRUCTIONS:
#   - View changes: `-` prefix = removed, `+` prefix = added
#   - Edit content: Modify `+` lines to change the proposed content
#   - To add new content: Write it without a prefix (context) or with `+`
#   - Modified `-` lines? Harmless — they get discarded automatically
#   - Exit: :q  (single file = single exit, NO vimdiff confusion)
# ==========================================================================
# Below is the diff. Edit freely. Only `-` lines are discarded on save.
# ==========================================================================

"""
    return header + diff_text
```

### Step 2: Update `preview_edit_diff_viewer()` CLI editor branch

- **File:** [src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py](/src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py)
- **Change:** In the `if _is_cli_editor(diff_viewer):` block of `preview_edit_diff_viewer()`, replace the current vimdiff flow with the annotated diff approach. The current CLI branch (lines ~145-157) does:

```python
if _is_cli_editor(diff_viewer):
    import subprocess
    try:
        with app.suspend():
            subprocess.run(diff_viewer + [str(before), str(p_file)])
            _restore_foreground_process_group()
            _restore_terminal_cooked_mode()
        _flush_stdin()
        harvest_edit_diff(action, p_file, original, proposed)
        app._system_env.delete_file(before)
        return True
    except Exception as e:
        logger.debug("Failed to run CLI diff viewer: %s", e)
        app._system_env.delete_file(before)
        return False
```

Replace the entire `if _is_cli_editor:` block with:

```python
if _is_cli_editor(diff_viewer):
    import subprocess
    import tempfile

    # Generate annotated diff content
    path_str = cast(str, action.params.get("path", ""))
    diff_content = _generate_annotated_diff_content(original, proposed, path_str)

    # Create temp file with .diff extension for syntax highlighting
    annotated_file = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".diff",
        prefix="teddy_edit_diff_",
        delete=False,
        encoding="utf-8",
    )
    annotated_path = annotated_file.name
    annotated_file.write(diff_content)
    annotated_file.close()

    try:
        with app.suspend():
            # Use the editor command WITHOUT diff flags — single file
            subprocess.run(diff_viewer[:1] + [annotated_path])
            _restore_foreground_process_group()
            _restore_terminal_cooked_mode()
        _flush_stdin()

        # Read back and reconstruct
        with open(annotated_path, "r", encoding="utf-8") as f:
            edited_content = f.read()
        final_content = reconstruct_from_diff(edited_content)

        # Harvest if content changed
        if final_content and final_content != proposed:
            action.params["edits"] = [{"find": original, "replace": final_content}]
            action.params.pop("content", None)

        return True
    except Exception as e:
        logger.debug("Failed to run annotated diff editor: %s", e)
        return False
    finally:
        try:
            os.unlink(annotated_path)
        except OSError:
            pass
```

**Important:** The `before` file created by `_setup_before_file()` is no longer needed for the annotated diff path. Move the `before = _setup_before_file(app, path_str, original)` call inside the GUI editor branch (the `else` clause) to avoid creating an unused temp file. See Step 3.

### Step 3: Remove unnecessary `before` file creation in CLI path

- **File:** [src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py](/src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py)
- **Change:** In `preview_edit_diff_viewer()`, the line `before = _setup_before_file(app, path_str, original)` currently runs unconditionally before the branch. Move it inside the GUI editor branch so that CLI editors don't create it:

```python
# Before the branch:
p_file = action.pending_temp_file
if p_file and isinstance(p_file, (str, os.PathLike)):
    if handle_mock_diff(p_file, before, app._system_env.delete_file):
        return True
    prepare_after_file(p_file, proposed)

    if _is_cli_editor(diff_viewer):
        # Annotated diff flow (no before file needed)
        # ... code from Step 2 ...
    else:
        before = _setup_before_file(app, path_str, original)
        try:
            app._system_env.run_command(
                diff_viewer + [str(before), str(p_file)],
                background=True,
            )
        except Exception as e:
            logger.debug("Failed to launch diff viewer: %s", e)
```

This ensures `_setup_before_file` is only called for the GUI path that actually uses it.

### Step 4: Update tests

- **File:** [tests/suites/unit/adapters/inbound/test_tui_editor_suspend_resume.py](/tests/suites/unit/adapters/inbound/test_tui_editor_suspend_resume.py)
- **Change:** Update `TestPreviewEditDiffViewer` to cover the annotated diff flow:
  - Test that CLI editor branch creates an annotated `.diff` file (via `tempfile.NamedTemporaryFile` with `.diff` suffix)
  - Test that `reconstruct_from_diff()` works correctly with various diff inputs (additions only, deletions only, mixed, empty diff)
  - Test that modified `-` lines are discarded during reconstruction
  - Test that modified `+` lines are kept during reconstruction
  - Test that `_generate_annotated_diff_content()` produces valid unified diff header and content
  - Existing GUI editor tests should remain unchanged

- **File:** [tests/suites/unit/adapters/inbound/test_reviewer_app_core.py](/tests/suites/unit/adapters/inbound/test_reviewer_app_core.py)
- **Change:** Update any tests that reference the old vimdiff behavior (e.g., checking that `preview_edit_diff_viewer` opens two files). They should now check for the single-file annotated diff flow.

### Step 5: Clean up old vimdiff code (optional but recommended)

- **File:** [src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py](/src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py)
- **Change:** Remove the `_setup_before_file()` function if it's no longer used outside the GUI branch. Remove the `before` parameter from `handle_mock_diff` if it's no longer needed. Delete the old `harvest_edit_diff()` function if it's replaced by inline harvest logic. Verify no other callers remain.

## Verification

1. Run the full test suite: `uv run pytest` — all tests must pass.
2. Run unit tests for the editor module: `uv run pytest tests/suites/unit/adapters/inbound/test_tui_editor_suspend_resume.py -v`
3. Run unit tests for the console tooling: `uv run pytest tests/suites/unit/adapters/outbound/test_console_tooling_editor.py -v`
4. Manually verify in TUI:
   - Press `e` on an EDIT action with vim/nvim as editor — a single `.diff` file opens with annotated changes. `:q` exits cleanly (no single-column confusion).
   - Edit a `+` line — the edit appears in the reconstructed content.
   - Edit a `-` line — the edit is discarded (reconstructed content matches expected).
   - Press `e` on an EDIT action with a GUI editor (code/cursor) — the existing `code --diff` flow works unchanged.
5. Verify reconstruction edge cases:
   - Empty diff (original == proposed) — `reconstruct_from_diff` returns the original content.
   - Only additions — `+` lines are correctly kept, `-` lines absent.
   - Only deletions — `-` lines are discarded, context lines kept, no `+` lines.
   - Mixed modifications — both additions and deletions handled correctly.
6. Verify no regressions in CREATE, EXECUTE, RESEARCH, and READ action previews.
