# Slice: System Info Token Visibility
- **Status:** Completed
- **Type:** Feature
- **Milestone:** N/A (Ad-hoc)
- **Specs:** [docs/project/tasks/00-02-system-info-token-visibility.md](/docs/project/tasks/00-02-system-info-token-visibility.md)
- **Prototype:** N/A
- **Component Docs:** [docs/architecture/core/domain/project_context.md](/docs/architecture/core/domain/project_context.md), [docs/architecture/core/services/context_service.md](/docs/architecture/core/services/context_service.md), [docs/architecture/adapters/inbound/textual_plan_reviewer.md](/docs/architecture/adapters/inbound/textual_plan_reviewer.md)
- **Scope Slug:** `system-info-token-visibility`

## Business Goal

Display system information tokens (project tree, git status, headers, formatting) as part of the "System" line in the TUI's context detail pane, so users can see a complete and accurate token breakdown for the LLM context.

## Scenarios

> As a user, I want to see the total context token count accurately reflect all content sent to the LLM, so that I can make informed decisions about context management.

```gherkin
Given the ContextService has assembled the project context
When the ProjectContext is created
Then it should contain a content_tokens field with the token count of the full content string
```

> As a user viewing the TUI context detail pane, I want to see a merged "System" line that includes both system prompt tokens and system info tokens, so that the breakdown sums to the total context.

```gherkin
Given the TUI context detail pane is displayed with the Context Root selected
When the "System" line is rendered
Then it should show the sum of system_prompt_tokens and system_info_tokens
And the "Total Context" should equal content_tokens + system_prompt_tokens
```

## Edge Cases

- **No files selected**: If `selected_file_tokens == 0`, `system_info_tokens` should equal `content_tokens` and System should show all of it plus the system prompt.
- **include_tokens=False**: When token counting is disabled, `content_tokens` should be 0.
- **Empty content**: If the content string is empty, `content_tokens` should be 0.

## Implementation Plan

Three atomic deliverables following the Contract -> Logic -> Wiring sequence:

1. **Contract**: Add `content_tokens: int = 0` field to `ProjectContext` dataclass (after `system_prompt_tokens`).
2. **Logic**: In `ContextService.get_context()`, after assembling `content`, compute its token count via `self._llm_client.get_text_token_count(content)` and pass `content_tokens=content_tokens` to the `ProjectContext` constructor. If `include_tokens` is False, set `content_tokens` to 0.
3. **Wiring**: In `populate_context_detail()`, compute `system_info_tokens = app.project_context.content_tokens - sum(selected_item token_count)`, update `Total Context` to `content_tokens + system_prompt_tokens`, and update `• System` to show the merged sum.

## Deliverables

- [x] **Contract** - Add `content_tokens` field to `ProjectContext` dataclass
- [x] **Logic** - Compute `content_tokens` in `ContextService.get_context()`
- [x] **Wiring** - Update TUI detail pane to derive `system_info_tokens` and show merged System line

## Implementation Notes

### Contract (Deliverable 1)
- Added `content_tokens: int = 0` field to `ProjectContext` dataclass after `system_prompt_tokens` in `src/teddy_executor/core/domain/models/project_context.py`.
- Backward-compatible default of 0 ensures no existing callers break.

### Logic (Deliverable 2)
- In `ContextService.get_context()`, after assembling the `content` string, computed `content_tokens = self._llm_client.get_text_token_count(content)`.
- Passed `content_tokens=content_tokens` to the `ProjectContext` constructor.
- When `include_tokens=False`, `content_tokens` is set to 0 and `_llm_client.get_text_token_count` is not called.
- Updated tests in `test_context_service.py` to verify `content_tokens` computation and zero-case.

### Wiring (Deliverable 3)
- In `populate_context_detail()` in `textual_plan_reviewer_helpers.py`:
  - Computed `system_info_tokens = app.project_context.content_tokens - selected_file_tokens`.
  - Updated `Total Context` to `content_tokens + system_prompt_tokens`.
  - Updated `• System` to show merged sum `system_prompt_tokens + system_info_tokens`.
- Tree node for agent name under "System:" remains unchanged (still shows only `system_prompt_tokens`).
- Session, Turn, History lines remain unchanged.
- Fixed two Local Flaws in existing tests that were missing the `content_tokens` field:
  - `test_context_display_helpers.py`: added `content_tokens=1500`.
  - `test_reviewer_app_context_previews.py`: added `content_tokens=1500` and `content_tokens=8200` for two test functions.

### As-Built Updates
- Updated `docs/architecture/core/domain/project_context.md` to document `content_tokens` attribute.
- Updated `docs/architecture/core/services/context_service.md` to document `content_tokens` computation in `get_context()`.
- Updated `docs/architecture/adapters/inbound/textual_plan_reviewer.md` to document merged System line in context detail pane.

## Verification

- [x] 1. Run the existing test suite to confirm no regressions:
   ```shell
   poetry run pytest -x
   ```
- [x] 2. Verify `content_tokens` is computed correctly by checking that `token_count(content)` matches what the LLM sees.
   - Covered by `test_get_context_computes_content_tokens` and `test_get_context_content_tokens_zero_when_include_tokens_false` in `test_context_service.py`.
- [x] 3. Check edge case: when no files are selected (`selected_file_tokens == 0`), `system_info_tokens` should equal `content_tokens` and System should show all of it plus the system prompt.
   - Covered by `test_populate_context_detail_system_info_tokens_equals_content_tokens_when_no_files_selected` in `test_textual_plan_reviewer_helpers.py`.
