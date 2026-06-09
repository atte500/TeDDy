# Task: Add Current Turn to Input.md, EXECUTE Tail, READ Lines Range, and Prompt Updates

## Business Goal
Improve the agent's situational awareness (input.md turn info) and provide more flexible output control (EXECUTE last N lines, READ line range) with proper documentation across all agent prompts.

## Context

### Change 1: Add Current Turn to Input.md System Information
- **Why:** Agents need to know which turn they're on (e.g., "Turn 01 of 99") for contextual awareness during session execution.
- **Current behavior:** `context_service.py` `_format_header()` builds a header from a `system_info` dict containing `current_date`, `current_time`, `cwd`, `os_name`, `os_version`, `shell`.
- **Target:** Add `- **Current Turn:** N` line to the header. The turn number is formatted as a zero-padded 2-digit string (e.g., "01", "99") and is available from the session context (pass as optional parameter to `get_context()` and `_format_header()`).
- **Key files:**
  - `src/teddy_executor/core/services/context_service.py` — `_format_header()` (approx line 274-285) and `get_context()` (approx line 42-80)
  - Callers of `get_context()` (possibly `session_orchestrator.py` or `execution_orchestrator.py`) must pass the turn number.

### Change 2: EXECUTE — Optional `Tail` Parameter (Override Last N Lines)
- **Why:** Agents need to limit EXECUTE output to the last N lines without relying on hardcoded defaults.
- **Current behavior:** The `ShellAdapter` has `max_execute_lines` (default 100) and calls `truncate_lines(content, max_lines, direction="tail")`. The `parse_execute_action()` function in `action_parser_complex.py` defines a `text_key_map` for extracting parameters like `Background`, `Timeout`, `Allow Failure` from the action's metadata list. There is currently no parameter to override the output line limit.
- **Target:** Add `Tail` (capital T, integer) as an optional parameter to EXECUTE. When present, its value overrides `max_execute_lines` as the `max_lines` argument to `truncate_lines`. The parameter should flow: parser → ActionData.params → action_executor.py → shell_adapter.py.
- **Key files:**
  - `src/teddy_executor/core/services/action_parser_complex.py` — `parse_execute_action()` (text_key_map at line ~121)
  - `src/teddy_executor/adapters/outbound/shell_adapter.py` — `execute_command()` (truncation logic at lines ~182-185)
  - `src/teddy_executor/core/services/action_executor.py` — EXECUTE dispatch/handler
  - `src/teddy_executor/core/domain/models/plan.py` — ActionData model (may need to check if params dict is sufficient)

### Change 3: READ — Optional `Lines` Range Parameter
- **Why:** Agents need to read specific line ranges of a file (e.g., lines 10-50) and bypass truncation limits when a range is specified.
- **Current behavior:** READ is dispatched in `action_dispatcher.py` (line 90) and executed via `_file_system_manager.read_file(path)` in `action_executor.py` (lines 66, 83). The file content is then potentially truncated.
- **Target:** Add `Lines` parameter to READ (e.g., `10-50`) that specifies a line range. After reading the full file content, extract only the specified lines. When `Lines` is specified, truncation should be bypassed (the agent explicitly asked for a specific range).
- **Key files:**
  - `src/teddy_executor/core/services/action_dispatcher.py` — READ dispatch (line 90)
  - `src/teddy_executor/core/services/action_executor.py` — `_handle_read` or `read_file` calls
  - `src/teddy_executor/core/services/action_parser_complex.py` — READ parsing (if there is a `parse_read_action` function)
  - `src/teddy_executor/core/services/action_parser_strategies.py` — possibly READ parsing strategy

### Change 4: Update All 6 Agent Prompt Files with New Parameter Documentation
- **Why:** All agent prompts (pathfinder, architect, developer, debugger, assistant, prototyper) document EXECUTE and READ action syntax. The new optional parameters (`Tail` for EXECUTE, `Lines` for READ) must be documented in each prompt.
- **Target:** Update the `<action>` block for EXECUTE and READ in each of the 6 XML prompt files.
- **Key files:**
  - `src/teddy_executor/resources/prompts/pathfinder.xml`
  - `src/teddy_executor/resources/prompts/architect.xml`
  - `src/teddy_executor/resources/prompts/developer.xml`
  - `src/teddy_executor/resources/prompts/debugger.xml`
  - `src/teddy_executor/resources/prompts/assistant.xml`
  - `src/teddy_executor/resources/prompts/prototyper.xml`

## Implementation Steps

### Step 1: Add `current_turn` Parameter to `_format_header` and `get_context`
- **File:** [src/teddy_executor/core/services/context_service.py](/src/teddy_executor/core/services/context_service.py)
- **Change:**
  1. Modify `_format_header(self, system_info: Dict[str, str], current_turn: Optional[str] = None) -> str` signature.
  2. Add the following line inside `_format_header` after the `Shell` line:
     ```python
     f"- **Current Turn:** {system_info.get('current_turn', current_turn or 'N/A')}",
     ```
  3. Modify `get_context(self, ..., current_turn: Optional[str] = None, ...)` to accept `current_turn` parameter.
  4. Inside `get_context`, before building `ProjectContext`, add `system_info['current_turn'] = current_turn` if `current_turn` is not None.
  5. Update the call to `_format_header(system_info)` to `_format_header(system_info, current_turn)` (already have `current_turn` as local var from parameter).
  6. Update any callers of `get_context()` (e.g., `session_orchestrator.py`, `execution_orchestrator.py`) to pass the current turn number. The turn number is typically available as a 2-digit string from the session's current turn directory (e.g., `"01"`).

### Step 2: Add `Tail` Parameter to EXECUTE Parsing
- **File:** [src/teddy_executor/core/services/action_parser_complex.py](/src/teddy_executor/core/services/action_parser_complex.py)
- **Change:**
  1. In `parse_execute_action()`, add `"Tail": "tail"` to the `text_key_map` dictionary (approx line 121-122). This extracts the `Tail` parameter from the metadata list as `params["tail"]`.
  2. Ensure the `tail` value is validated as an integer (or convert to int when used later).

### Step 3: Pass `Tail` Parameter Through ActionExecution to ShellAdapter
- **File:** [src/teddy_executor/core/services/action_executor.py](/src/teddy_executor/core/services/action_executor.py)
- **Change:**
  1. Locate where EXECUTE actions are dispatched and the shell adapter is called.
  2. Extract `tail` from `action.params` (e.g., `tail_str = action.params.get("tail")`).
  3. If present, convert to int: `tail = int(tail_str)`.
  4. Pass `tail` as a keyword argument to the shell adapter's `execute_command()` method (or to the truncation call). If the `ShellAdapter.execute_command` already accepts `max_lines` as a parameter, pass it. Otherwise, add it.

### Step 4: Handle `Tail` Parameter in ShellAdapter Truncation Logic
- **File:** [src/teddy_executor/adapters/outbound/shell_adapter.py](/src/teddy_executor/adapters/outbound/shell_adapter.py)
- **Change:**
  1. In `execute_command()` (or wherever output truncation occurs, approx lines 182-185), check if an explicit `tail` (or `max_lines`) override was passed.
  2. If provided, use that value as the `max_lines` argument to `truncate_lines()` instead of the default `max_execute_lines`.
  3. Example logic:
     ```python
     max_lines = max_lines_override if max_lines_override is not None else self.max_execute_lines
     content = truncate_lines(content, max_lines, direction="tail")
     ```

### Step 5: Add `Lines` Parameter to READ Parsing
- **File:** [src/teddy_executor/core/services/action_parser_complex.py](/src/teddy_executor/core/services/action_parser_complex.py) (the READ parsing likely happens here; search for `parse_read_action` or similar)
- **Change:**
  1. Locate the READ parsing function.
  2. Add extraction of the `Lines` parameter from the metadata list. E.g., `lines = params.get("Lines")`.
  3. Store it in the action data (e.g., `action.params["lines"]`).
- **File:** [src/teddy_executor/core/services/action_dispatcher.py](/src/teddy_executor/core/services/action_dispatcher.py)
- **Change:**
  1. In the READ dispatch logic (line 90), pass the `lines` parameter from the action to the executor method.

### Step 6: Apply `Lines` Range in READ Execution
- **File:** [src/teddy_executor/core/services/action_executor.py](/src/teddy_executor/core/services/action_executor.py)
- **Change:**
  1. Locate the method that handles READ action execution (where `read_file` is called, lines 66 and 83).
  2. After reading the file content into `content`, if `action.params` contains `lines`:
     - Parse the range string (e.g., `"10-50"`) into `start_line` and `end_line` integers (1-indexed).
     - Split `content` by newlines.
     - Extract `lines[start_line-1:end_line]` (inclusive of both ends).
     - Rejoin and use this as the new content.
  3. When `lines` is specified, skip truncation of the output (the agent explicitly requested a range, so no need for `[Content truncated...]` hint).
  4. Handle edge cases: `10-10` (single line), `-20` (first 20 lines), `50-` (from line 50 to end), or out-of-range gracefully.

### Step 7: Update All 6 Prompt Files
- **File:** [src/teddy_executor/resources/prompts/pathfinder.xml](/src/teddy_executor/resources/prompts/pathfinder.xml)
- **Change:** In the EXECUTE `<action>` block, document the new optional `Tail` parameter. In the READ `<action>` block, document the new optional `Lines` parameter.

- **File:** [src/teddy_executor/resources/prompts/architect.xml](/src/teddy_executor/resources/prompts/architect.xml)
- **Change:** Same as above — update EXECUTE and READ documentation.

- **File:** [src/teddy_executor/resources/prompts/developer.xml](/src/teddy_executor/resources/prompts/developer.xml)
- **Change:** Same as above.

- **File:** [src/teddy_executor/resources/prompts/debugger.xml](/src/teddy_executor/resources/prompts/debugger.xml)
- **Change:** Same as above.

- **File:** [src/teddy_executor/resources/prompts/assistant.xml](/src/teddy_executor/resources/prompts/assistant.xml)
- **Change:** Same as above.

- **File:** [src/teddy_executor/resources/prompts/prototyper.xml](/src/teddy_executor/resources/prompts/prototyper.xml)
- **Change:** Same as above.

The documentation for EXECUTE should look like:
```xml
- **`Tail`** (Optional integer, e.g., `20`): Override the default output line limit. Only the last N lines of output are returned. Useful for very verbose commands.
```

The documentation for READ should look like:
```xml
- **`Lines`** (Optional string, e.g., `10-50`): Read only the specified line range from the file. Supports formats: `start-end` (inclusive), `-end` (from beginning), `start-` (to end), or a single line number. When set, the file's truncation limit is bypassed.
```

## Verification

1. **Input.md Turn N:** Run a session turn and verify `input.md` contains `- **Current Turn:** 01` (or appropriate number) in the System Information section.
2. **EXECUTE Tail:** Create a plan with `### `EXECUTE`` containing `- **Tail:** `5`` and a command that outputs 20+ lines. Verify only the last 5 lines appear in the execution report, with appropriate truncation hint.
3. **EXECUTE Tail (default behavior):** Run EXECUTE without `Tail` parameter. Verify it still uses the default `max_execute_lines` (100) and truncation hint is shown.
4. **READ Lines:** Create a plan with `### `READ`` containing `- **Lines:** `10-20`` on a file with 30+ lines. Verify only lines 10-20 are returned in the execution report, without a `[Content truncated...]` hint.
5. **READ Lines (edge cases):** Test `- **Lines:** `1-5`` (first 5), `- **Lines:** `-10`` (from line 10 to end), `- **Lines:** `5`` (single line 5).
6. **Prompt files:** Grep each of the 6 prompt files for `Tail` and `Lines` documentation to confirm they were updated.
7. **Existing tests pass:** Run the full test suite to ensure no regressions.
