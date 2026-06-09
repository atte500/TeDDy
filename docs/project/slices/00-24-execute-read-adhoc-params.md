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
- [x] **Logic** - Add `current_turn` parameter to `ContextService._format_header()` and `get_context()`, and propagate to callers (`session_orchestrator.py`, `execution_orchestrator.py`).
- [x] **Seam** - Add `Tail` optional parameter extraction in EXECUTE parsing (`parse_execute_action` in `action_parser_complex.py`).
- [x] **Logic** - Pass `Tail` parameter through `ActionExecutor` to `ShellAdapter` and apply in truncation logic.
- [▶] **Seam** - Add `Lines` optional parameter extraction in READ parsing (`action_parser_strategies.py` or `action_parser_complex.py`).
- [ ] **Logic** - Apply `Lines` range in READ execution within `ActionExecutor` (in `_handle_read`).
- [ ] **Documentation** - Update all 6 agent prompt files with new parameter docs.
- [ ] **Wiring** - Update `session_orchestrator.py` to pass `current_turn` extracted from `Path(plan_path).parent.name` to `get_context()`.
- [ ] **Wiring** - Update `planning_service.py` to pass `current_turn` extracted from `turn_dir` to `get_context()`.
- [ ] **Wiring** - Integration test verifying end-to-end flow for EXECUTE Tail override and READ Lines range.

## Implementation Notes

### Deliverable 1: current_turn Parameter
- Added `current_turn: Optional[str] = None` to `IGetContextUseCase.get_context()` interface signature in `get_context_use_case.py`.
- Added the parameter to `ContextService.get_context()` in `context_service.py` and passed it to `_format_header()`.
- Updated `_format_header()` to accept `current_turn` and added `- **Current Turn:** {current_turn or 'N/A'}` as the last header line.
- Updated existing test `test_get_context_orchestrates_and_returns_correct_dto` to assert default "N/A" behavior.
- Added new test `test_get_context_with_current_turn_parameter` to verify "01" is rendered when passed.
- **Critical finding:** `execution_orchestrator.py` does NOT call `get_context()` (confirmed via grep). Only `session_orchestrator.py` and `planning_service.py` are direct callers. The parameter is optional with a default of None, so all callers continue to work without changes. However, best practice would have `session_orchestrator.py` pass the turn number from `Path(plan_path).parent.name`, and `planning_service.py` pass it from `turn_dir`. These are tracked as separate deliverables below.

### Technical Debt: PLR0913 Parameter Count
- `get_context()` has 6 parameters (excluding self) vs ruff's PLR0913 threshold of 5. The function was already at the boundary (5 params) before adding `current_turn`. A proper fix would require bundling parameters into an options dataclass, which is a breaking change to the public interface. Logged as acceptable debt for now.

### Deliverable 2: Tail Parameter Extraction (Seam)
- Added `"Tail": "tail"` to the `text_key_map` dictionary in `parse_execute_action()` within `action_parser_complex.py`.
- The `Tail` parameter is extracted as a string value (e.g., `"5"`) stored in `action.params["tail"]`.
- The `MarkdownPlanBuilder.add_execute` passes kwargs as-is, so test uses `Tail=5` (uppercase T) to match the spec format.
- The parameter is optional and backward-compatible: existing tests that don't pass `Tail` continue to work unchanged.
- Integer conversion of the tail value happens in the downstream Logic deliverable (Deliverable 3) when passing it to `ShellAdapter`.

### Deliverable 3: Tail Parameter Propagation (Logic)
- **Contract (Protocol):** Added `max_lines: Optional[int] = None` to `IShellExecutor.execute()` in `shell_executor.py` — backward-compatible optional parameter.
- **Adapter (Threading):** Threaded `max_lines` through `ShellAdapter.execute()` → `_run_subprocess()` → `_process_execution_results()`:
  - `_process_execution_results()` now accepts `max_lines: Optional[int] = None` and uses `max_lines if max_lines is not None else self.max_execute_lines` as the effective limit.
- **Dispatch (Conversion):** Updated `ActionFactory._handle_execute_protocol()` to extract `tail` from kwargs, convert to int via `int(tail)`, and pass as `max_lines` to the shell executor. Invalid/zero/negative values are silently ignored (falls back to default).
- **Test:** Added `test_shell_adapter_process_execution_results_with_max_lines_override` in `test_shell_adapter_capping.py` — verifies that a `max_lines=3` override truncates to 3 lines + hint regardless of the adapter's `max_execute_lines=100`.
- **Key insight:** The `tail` value from `action.params["tail"]` is a string (`"5"`). Conversion must happen at the dispatch layer (ActionFactory) before it reaches the protocol signature.

### Deliverable 4 (Pending): READ Lines Parameter Extraction
- Need to locate the READ parsing function (likely `action_parser_strategies.py`).
- Add `"Lines": "lines"` to the relevant `text_key_map` or metadata extraction.
- Add test(s) for `Lines` parameter extraction in READ parsing tests.

## Implementation Plan
The changes are additive: add optional parameters to existing functions. No breaking changes. Each deliverable follows the Developer workflow: Red (write/update tests), Green (implement minimal code), Refactor. Integration tests and prompt file updates are handled as separate deliverables. The Wiring deliverable at the end will verify end-to-end behavior via a `CliRunner` acceptance test.

## Implementation Plan
The changes are additive: add optional parameters to existing functions. No breaking changes. Each deliverable follows the Developer workflow: Red (write/update tests), Green (implement minimal code), Refactor. Integration tests and prompt file updates are handled as separate deliverables. The Wiring deliverable at the end will verify end-to-end behavior via a `CliRunner` acceptance test.
