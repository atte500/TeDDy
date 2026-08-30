# Bug: TUI READ URL Preview Shows Empty File When Using GUI Editor
- **Status:** Resolved
- **Milestone:** [Milestone 4: TUI & UX Enhancements](/docs/project/milestones/04-tui-ux-enhancements.md)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

Pressing `e` on a READ action whose resource is a URL (e.g., `https://example.com/file.md`) opens the configured GUI editor (e.g., `code`, `codium`, `cursor`) to a **new, empty file** — the actual scraped Markdown content is not visible. The user sees an empty editor buffer.

CLI editors (e.g., `vim`, `nvim`) display the content correctly.

**Expected:** The editor opens showing the extracted Markdown content in a `.md` file.
**Actual:** GUI editors show an empty buffer (the file existed temporarily but was deleted before the editor read it).

**Minimal reproduction:**
1. Configure a GUI editor (e.g., `editor: "codium"`) in `.teddy/config.yaml`.
2. Create a plan with a READ action whose resource is `https://example.com`.
3. Press `e` in the TUI to preview the READ action.
4. Observe: the editor opens to an empty file buffer.
5. Repeat with a CLI editor (e.g., `editor: "nvim"`): content is visible correctly.

## Context & Scope

### Regressing Delta
The empty-file bug was introduced by commit `1fee80b1` (`fix(tui): fetch URL content for READ preview and skip ConfirmScreen for GUI editors`), which added the URL content-fetching and temp-file write to `preview_readonly()`. The temp file lifecycle is:

1. Fetch content via `app._web_scraper.get_content(resource)` (wired in commit `1e92e379`).
2. Write content to a `teddy_read_url_*.md` temp file.
3. Open editor.
4. Immediately call `os.unlink(temp_path)` after editor launch.

**Steps 1-2 (fetch and write) are correct** — content is flushed to disk before any editor is launched. Step 4 is the problem:

- **CLI branch (line ~201):** `subprocess.run()` runs **synchronously** inside `app.suspend()` → editor reads the file, exits, THEN `os.unlink()` runs → content visible.
- **GUI branch (line ~213):** `spawn_editor()` is a **non-blocking** `subprocess.Popen()` that returns immediately → `.unlink()` runs on the next line → GUI editors (code, codium, cursor, TextEdit) open the path asynchronously and find the file already deleted → **empty buffer**.

The later commit `1e92e379` (`fix(tui): route READ URL preview through existing WebScraper port`) did not change the temp-file lifecycle — it only replaced `_fetch_url_content()` with the WebScraper port.

### Environmental Triggers
- Configured GUI editor (`code`, `codium`, `cursor`, `subl`, etc.).
- READ action with `resource`/`path` set to an `http://` or `https://` URL.
- Does NOT trigger for CLI editors (`vim`, `nvim`, `nano`, etc.) because `subprocess.run()` blocks until the editor exits.

### Ruled Out
- **Write defect:** The unit test `test_readonly_url_fetches_content_and_opens_temp_file` asserts `write(expected_content)` and `close()`. Content is written and flushed correctly. Not a write issue.
- **Fetch defect:** The WebScraper port (`get_content`) returns extracted Markdown correctly; the guard for empty content prevents creating files when no content is extracted. Verified by test `test_readonly_url_fetch_failure_notifies_user`.
- **CLI editor path:** Works correctly — content is visible because `subprocess.run()` blocks. User confirmed CLI path works.
- **Non-URL READ actions:** Local file READ actions open the real file directly (no temp file) — they are unaffected.

## Diagnostic Analysis

### Causal Model
`preview_readonly()` in `textual_plan_reviewer_previews.py` (lines 138-214):

1. Extracts `resource` from action params.
2. If URL: fetches content via `app._web_scraper.get_content(resource)`; writes to temp file; gets `temp_path`.
3. If CLI editor: `subprocess.run(editor_cmd + [temp_path])` inside `app.suspend()` — **synchronous** — editor reads file, exits, execution continues to step 4.
4. If GUI editor: `spawn_editor(editor_cmd, temp_path)` — **returns immediately** (Popen). Execution continues to step 4 without waiting.
5. `os.unlink(temp_path)` — deletes the temp file.

For GUI editors, the editor process hasn't yet read the file (it's still being spawned/loaded) when `os.unlink` runs. The editor opens an empty buffer or shows "file not found".

### Discrepancies
- (Resolved: Turn 3, 2026-08-30) User confirmed editor is "codium" — a GUI editor. This validates the race-condition model. The CLI path works; GUI path fails. (Resolution: the diagnosis is confirmed.)

### Investigation History
1. **Turn 1 (2026-08-30):** Traced the full URL READ pipeline: `preview_readonly()` → `app._web_scraper.get_content()` → write `teddy_read_url_*.md` → open editor → `os.unlink(temp_path)`. Identified the GUI editor + immediate unlink as the prime suspect.
2. **Turn 2 (2026-08-30):** Examined `spawn_editor()` implementation — confirmed it uses `subprocess.Popen()` (non-blocking, returns immediately). Reviewed how EDIT/CREATE previews persist temp files: they use `app._system_env.create_temp_file()` and do NOT delete them immediately. URL READ preview is the only path that creates a `NamedTemporaryFile(delete=False)` and then immediately `os.unlink()`s after spawning the editor. Git diff of commit `1fee80b1` confirmed the post-spawn unlink was introduced in the original URL preview feature.
3. **Turn 3 (2026-08-30):** Alignment gate with user — confirmed editor is "codium" (GUI editor). Proposed creating Case File #38 and delegating to Debugger. User approved: "ok proceed".
4. **Turn 4 (2026-08-30):** Creating Case File #38 and preparing Debugger handoff.

## Solution

### Root Cause
The temp file created for URL READ preview content is deleted (`os.unlink`) immediately after the editor is launched, without waiting for the editor to read it. CLI editors (subprocess.run, synchronous) work because they read the file before the unlink executes. GUI editors (Popen, asynchronous) lose the race: the file is deleted before the editor process reads it.

### Fix Direction
Apply the same temp-file persistence strategy used by EDIT/CREATE previews and `view_details_handler`:

**For GUI editors (the `else` branch in `preview_readonly()`):**
- Do NOT call `os.unlink(temp_path)` immediately.
- Instead, track the temp file for cleanup on TUI exit using the existing `app._log_preview_files` list (same pattern as `view_details_handler` at line 238).
- The file lives for the duration of the TUI session and is cleaned up when the TUI exits (handled by `ReviewerApp.on_mount` cleanup at `textual_plan_reviewer_app.py:189-193, 221-225`).

**For CLI editors (the `if _is_cli_editor()` branch):**
- Keep the existing behavior: `subprocess.run()` blocks until the editor exits, so `os.unlink(temp_path)` is safe and immediate cleanup is fine.

**Regression test:**
- Add a test case `test_readonly_gui_url_does_not_unlink_before_editor_reads` that verifies `os.unlink` is NOT called for GUI editors with a URL resource, and that the temp file path is tracked for deferred cleanup.

### Preventative Measures
- All TUI preview/temp-file creation should use the same lifecycle strategy: persistent/retained temp files for GUI editors, immediate cleanup only when a synchronous process guarantees the file has been consumed.
- The debugger should audit all `os.unlink` calls in `textual_plan_reviewer_previews.py` to ensure no other branches have similar race conditions.
- Future preview features must add tests for both CLI and GUI editor paths.
