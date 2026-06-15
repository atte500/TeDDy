# Task: System Info Token Visibility in TUI

## Business Goal

Display system information tokens (project tree, git status, headers, formatting) as part of the "System" line in the TUI's context detail pane, so users can see a complete and accurate token breakdown for the LLM context.

## Context

Currently, the TUI right panel (context detail) shows a token breakdown when the Context Root is selected:

```
Total Context: 12.2k / 128k tokens
• System:     1.2k      ← only system_prompt_tokens
• Session:    5.2k
• Turn:       4.8k
• History:    2.2k
```

The "Total Context" is computed as `sum(selected item file tokens) + system_prompt_tokens`. This is **inaccurate** — it excludes all overhead tokens from:
- The `# Project Context` / `## System Information` header (date, time, CWD, OS, shell)
- The `## Git Status` section text
- The `## Project Structure` file tree (which can be hundreds of lines)
- All `---` separators, `### [path]` links, fenced codeblock markers, and section formatting

These overhead tokens are part of the formatted `ProjectContext.content` string sent to the LLM, but they're not attributed to any file or category.

**Solution:** Compute `content_tokens` (token count of the full content string) in `ContextService`, store it on `ProjectContext`, and derive `system_info_tokens` in the TUI as `content_tokens - sum(selected_file_tokens)`. Merged into the `• System` line.

**Two views (preserving the user's nuance):**
- **Tree node** for agent name under "System:" — stays unchanged, shows only `system_prompt_tokens`.
- **Overview detail pane** (right panel, Context Root selected) — merged `• System` line with both prompt and info.

**Terminal telemetry:** The `ProjectContext.content_tokens` field makes the accurate total content token count available for any terminal or telemetry output (e.g., `teddy context` summary). No immediate changes to terminal display are required, but the field ensures the total context token count is accurate wherever it may be displayed.

## Implementation Steps

### Step 1: Add `content_tokens` field to `ProjectContext`
- **File:** `src/teddy_executor/core/domain/models/project_context.py`
- **Change:** Add `content_tokens: int = 0` to the `ProjectContext` dataclass, after `system_prompt_tokens`.

### Step 2: Compute `content_tokens` in `ContextService.get_context()`
- **File:** `src/teddy_executor/core/services/context_service.py`
- **Change:** After assembling `content`, compute its token count via `self._llm_client.get_text_token_count(content)` and pass `content_tokens=content_tokens` to the `ProjectContext` constructor. If `include_tokens` is False, set `content_tokens` to 0.

### Step 3: Update TUI detail pane to use `content_tokens` and derive `system_info_tokens`
- **File:** `src/teddy_executor/adapters/inbound/textual_plan_reviewer_helpers.py`
- **Change:** In `populate_context_detail()`, update the Context Aggregate View block:
  - Compute `system_info_tokens = app.project_context.content_tokens - sum(selected_item token_count)`
  - Compute `total_tokens = app.project_context.content_tokens + app.project_context.system_prompt_tokens`
  - Update `Total Context` to display `total_tokens / window_val`
  - Update `• System` to display `(system_prompt_tokens + system_info_tokens) / 1000.0`
- **Important:** The tree node for the agent name under "System:" stays unchanged (still shows only `system_prompt_tokens`). The Session, Turn, and History lines remain unchanged.

## Verification

1. Run the existing test suite to confirm no regressions:
   ```shell
   poetry run pytest -x
   ```
2. Manually inspect the TUI by running a session with the Textual plan reviewer. Verify:
   - The tree node for the agent name under "System:" shows only `system_prompt_tokens` (unchanged).
   - The right panel (context detail) when Context Root is selected shows:
     - `Total Context` = `(content_tokens + system_prompt_tokens)` with correct window limit.
     - `• System` line shows the merged sum (`system_prompt_tokens + system_info_tokens`), which is larger than before.
     - Session, Turn, History lines unchanged.
   - The breakdown sums to the Total: `System + Session + Turn + History == Total Context`.
3. Verify `content_tokens` is computed correctly by checking that `token_count(content)` matches what the LLM sees.
4. Check edge case: when no files are selected (`selected_file_tokens == 0`), `system_info_tokens` should equal `content_tokens` and System should show all of it plus the system prompt.
