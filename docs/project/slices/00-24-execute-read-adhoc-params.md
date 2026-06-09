# Slice: Execute READ Adhoc Params
- **Status:** In Progress
- **Type:** Feature
- **Milestone:** [N/A - Ad-hoc](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [Task Brief](/docs/project/tasks/24-execute-read-adhoc-params.md)
- **Component Docs:** [ContextService](/docs/architecture/core/services/context_service.md), [ActionExecutor](/docs/architecture/core/services/action_executor.md), [ShellAdapter](/docs/architecture/adapters/outbound/shell_adapter.md), [ActionParserComplex](/docs/architecture/core/services/action_parser_complex.md)

## Business Goal
Improve the agent's situational awareness (input.md turn info) and provide more flexible output control (EXECUTE last N lines, READ line range) with proper documentation across all agent prompts.

## Scenarios
> As an agent, I want to know which turn I'm on in the session, so that I can provide context-aware responses.
```gherkin
Given a session with multiple turns
When the context is gathered
Then the system information in input.md includes "- **Current Turn:** 01"
```

> As an agent, I want to limit EXECUTE output to the last N lines, so that I can handle verbose commands without overwhelming context.
```gherkin
Given an EXECUTE action with "- **Tail:** 5"
When the command produces more than 5 lines of output
Then only the last 5 lines appear in the execution report
```

> As an agent, I want to read a specific line range from a file, so that I can focus on relevant sections.
```gherkin
Given a READ action with "- **Lines:** 10-20"
When the file has 30+ lines
Then only lines 10-20 are returned in the execution report, without truncation hint
```

## Edge Cases
- **EXECUTE Tail zero or negative**: If Tail is <=0, default to max_execute_lines.
- **EXECUTE missing Tail**: Default behavior unchanged (max_execute_lines=100).
- **READ Lines out of range**: If start or end exceeds file length, clamp to file bounds.
- **READ Lines malformed**: If Lines format is invalid (e.g., "abc"), fall back to full file read.
- **No session turn number**: If current_turn is never passed, "N/A" is displayed.
- **Prompt updates**: All 6 prompts must be updated consistently.

## Deliverables
- [▶] **Logic** - Add `current_turn` parameter to `ContextService._format_header()` and `get_context()`, and propagate to callers (`session_orchestrator.py`, `execution_orchestrator.py`).
- [ ] **Seam** - Add `Tail` optional parameter extraction in EXECUTE parsing (`parse_execute_action` in `action_parser_complex.py`).
- [ ] **Logic** - Pass `Tail` parameter through `ActionExecutor` to `ShellAdapter` and apply in truncation logic.
- [ ] **Seam** - Add `Lines` optional parameter extraction in READ parsing (`action_parser_strategies.py` or `action_parser_complex.py`).
- [ ] **Logic** - Apply `Lines` range in READ execution within `ActionExecutor` (in `_handle_read`).
- [ ] **Documentation** - Update all 6 agent prompt files with new parameter docs.
- [ ] **Wiring** - Integration test verifying end-to-end flow for EXECUTE Tail override and READ Lines range.

## Implementation Notes
(To be filled during implementation)

## Implementation Plan
The changes are additive: add optional parameters to existing functions. No breaking changes. Each deliverable follows the Developer workflow: Red (write/update tests), Green (implement minimal code), Refactor. Integration tests and prompt file updates are handled as separate deliverables. The Wiring deliverable at the end will verify end-to-end behavior via a `CliRunner` acceptance test.
