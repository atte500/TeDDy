# Slice: Cap EXECUTE Output Length

- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config.md](../milestones/10-interactive-session-and-config.md)
- **Specs:** [report-format.md](../specs/report-format.md)

## Business Goal
Prevent massive shell output and large file reads from flooding the AI context and the UI, ensuring that only relevant information is presented while providing a path for the user to retrieve full data if necessary.

## Scenarios
> As a user, when I run a command that produces 10,000 lines of output, I want the execution report to only show the last 100 lines and a hint on how to view the full output so that the AI remains responsive and focused.

```gherkin
Given a plan with an EXECUTE action that produces 200 lines of output
And the execution output limit is set to 100 lines
When I execute the plan
Then the execution report should contain only the last 100 lines of stdout
And it should include a hint: "[Output truncated. Use 'command > file.txt' or 'grep' to filter results if needed.]"
```

> As a user, when I read a massive file (e.g., 5000 lines), I want the report to only show the first 1000 lines so that the context remains manageable.

```gherkin
Given a plan with a READ action for a file with 2000 lines
And the read output limit is set to 1000 lines
When I execute the plan
Then the execution report should contain only the first 1000 lines of the file
And it should include a hint: "[File content truncated. Use more specific search or 'grep' to find relevant sections.]"
```

## Deliverables
- [x] **Contract** - Add `max_execute_lines` (default 100) and `max_read_lines` (default 1000) to `IConfigService` and defaults.
- [x] **Logic** - Implement `truncate_lines(content, max_lines, direction="tail"|"head")` utility in `string.py`.
- [x] **Logic** - Apply truncation to `ShellAdapter` (tail).
- [x] **Logic** - Apply truncation to `LocalFileSystemAdapter` for `READ` (head).
- [x] **Logic** - Implement dynamic "hint" generation based on action type.
- [ ] **Wiring** - Wire config values to the adapters/services.
- [ ] **Refactor** - Prune any redundant full-output tests.

## Delta Analysis
- `src/teddy_executor/adapters/outbound/shell_adapter.py`: Add truncation in `_process_execution_results`.
- `src/teddy_executor/core/utils/string.py`: Add `truncate_tail` helper.
- `tests/suites/unit/adapters/outbound/test_shell_adapter_capping.py`: New tests for capping.

## Guidelines for Implementation
- Default cap: 100 lines.
- Truncation should only happen at the tail (last X lines).
- The hint should be clearly visible in the Markdown report.

## Implementation Notes
### Logic - Apply truncation to ShellAdapter (tail)
- Modified `ShellAdapter` to accept `max_execute_lines` in its constructor (default 100).
- Integrated `truncate_lines` into `_process_execution_results` to cap `stdout`.
- Added specific hint for shell output truncation: `[Output truncated. Use 'command > file.txt' or 'grep' to filter results if needed.]`.
- Verified with new unit tests in `test_shell_adapter_capping.py`.

### Logic - Apply truncation to LocalFileSystemAdapter (head)
- Modified `LocalFileSystemAdapter` to accept `max_read_lines` in its constructor (default 1000).
- Integrated `truncate_lines` into `read_file` to cap output at the head (first X lines).
- Added specific hint for file content truncation: `[File content truncated. Use more specific search or 'grep' to find relevant sections.]`.
- Verified with new unit tests in `test_file_system_adapter_capping.py`.

### Logic - Implement dynamic "hint" generation based on action type
- Implemented `get_truncation_hint(action_type: str)` in `src/teddy_executor/core/utils/string.py`.
- Centralized hints for "execute" and "read" actions.
- Refactored `ShellAdapter` and `LocalFileSystemAdapter` to use the new utility.
- Verified with unit tests in `test_string_utils.py` and updated adapter tests.
