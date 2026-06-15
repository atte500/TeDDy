# Slice: System Info Token Visibility
- **Status:** In Progress
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

- [ ] **Contract** - Add `content_tokens` field to `ProjectContext` dataclass
- [ ] **Logic** - Compute `content_tokens` in `ContextService.get_context()`
- [ ] **Wiring** - Update TUI detail pane to derive `system_info_tokens` and show merged System line

## Implementation Notes

To be filled during implementation.

## Verification

1. Run the existing test suite to confirm no regressions:
   ```shell
   poetry run pytest -x
   ```
2. Verify `content_tokens` is computed correctly by checking that `token_count(content)` matches what the LLM sees.
3. Check edge case: when no files are selected (`selected_file_tokens == 0`), `system_info_tokens` should equal `content_tokens` and System should show all of it plus the system prompt.
