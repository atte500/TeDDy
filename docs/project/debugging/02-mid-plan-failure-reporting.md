# Bug: Mid-Plan Failure Reports Incorrect Success

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](/docs/project/milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** N/A
- **Specs:** [report-format](/docs/project/specs/report-format.md)

## Symptoms
In a multi-action plan, if a state change caused by an earlier action (e.g., `EXECUTE`) causes a later action (e.g., `EDIT`) to fail its post-flight or execution checks (like matching content), the system incorrectly reports 'SUCCESS' instead of 'FAILURE'. This is currently observed on Windows runners.

## Context & Scope
### Regressing Delta
Unknown. The test `test_execute_mid_plan_failure_produces_report` is failing in CI.

### Environmental Triggers
- OS: Windows (confirmed in CI logs).
- Action sequence: `EXECUTE` (modifying file) -> `EDIT` (on same file).

### Ruled Out
- TUI/Interactive mode (the failing test uses `interactive=False`).

## Diagnostic Analysis
### Causal Model
1. `ActionDispatcher` executes actions via `ActionFactory` produced handlers.
2. `ActionDispatcher` defaults to `ActionStatus.SUCCESS` unless an exception is raised or a non-zero return code is returned.
3. `ShellCommandBuilder` identifies "complex" commands that require shell execution or special wrapping.
4. Redirection operators (`>`, `<`) are currently missing from the complexity detection logic.
5. On Windows, if a command contains redirection but is not flagged as "complex", and the first word (e.g., `echo`) exists as an external executable in the PATH, the command is executed with `shell=False`.
6. This causes the redirection operator to be treated as a literal argument to the executable rather than being interpreted by the shell, making the redirection a no-op.
7. Consequently, the file is not modified, but the executable returns 0, leading `ActionDispatcher` to report `SUCCESS`.
8. The subsequent `EDIT` action then finds the original content and succeeds, resulting in an overall `SUCCESS` report when a `FAILURE` was expected.

### Discrepancies
- The CI log shows `EDIT - Failing edit` followed by `SUCCESS`, even though the file content was changed by the preceding `echo`.

### Investigation History
1. Initial discovery from CI logs.
2. Identifying relevant files: `action_executor.py`, `edit_simulator.py`, `action_dispatcher.py`.
3. Observed that `ActionDispatcher` has a very permissive success condition.
4. Traced `EDIT` action to `LocalFileSystemAdapter.edit_file`.
5. Investigating `rstrip("\n")` in parsing and similarity threshold sensitivity as potential causes for incorrect success reporting on Windows.
6. Diagnostic probe confirmed that `ActionDispatcher` correctly reports `FAILURE` when an `EDIT` fails (at least on macOS).
7. Investigating `EditMatcher` and `EditSimulator` for line-ending sensitivity.
8. Examining `ExecutionOrchestrator` and `ExecutionReportAssembler` for status aggregation bugs.
9. Identified a potential collision/confusion between `ExecutionStatus` and `ActionStatus` enums. (Resolved: `ExecutionStatus` is unused in services).
10. Probing `EditMatcher` with exact test strings and checking bundled config for threshold overrides. (Resolved: Matcher works on macOS; config is 1.0).
11. Investigating `ShellAdapter` and `ShellCommandBuilder` for Windows redirection issues. Hypothesizing that `EXECUTE` succeeds without changing the file.
12. Checking `ActionDispatcher` success criteria and `shutil.which` behavior for builtins.
13. Identified missing redirection operators in `ShellCommandBuilder` complexity logic. Confirmed that `echo > file` is treated as simple, leading to `shell=False` if `echo.exe` exists.
14. Implemented fix in `ShellCommandBuilder` by adding `>` and `<` to the `ops` list for complexity detection.
15. Verified fix locally and confirmed via logic probe that Windows redirection now correctly triggers `use_shell=True`.
16. Executed global test suite; all tests passed, confirming no regressions.

## Solution
### Implemented Fixes
- Expanded the `ops` (shell operators) list in `ShellCommandBuilder.prepare` to include redirection operators (`>`, `<`), variable expansion (`$`, `%`), globbing (`*`, `?`), and subshells/grouping (`(`, `)`, `[`, `]`).
- This ensures that any command requiring shell interpretation is correctly identified as "complex," forcing `use_shell=True` (Windows) or `bash -c` (POSIX) execution.

### Prevention
- Added exhaustive shell metacharacters to the complexity detection logic to prevent future "silent execution failures" where `subprocess` might attempt to execute a shell-bound command as a literal binary call.
- The `test_execute_mid_plan_failure_produces_report` acceptance test now serves as a regression test for this scenario.
