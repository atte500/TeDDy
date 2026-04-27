# Slice: Session Context and UX Fixes
- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)

## Business Goal
Improve the clarity and reliability of TeDDy Sessions by refining the layout of the `input.md` file, ensuring context files correctly handle comments, preventing "context leakage" when actions fail, and removing redundant data from session execution reports.

## Scenarios

### Scenario 1: Initial User Request formatting in `input.md`
> As a user starting a session, I want my initial request to be clearly visible at the top of the `input.md` file so that I can easily verify the AI's instructions.
```gherkin
Given a new session is initialized
When the planning service generates the "input.md" file
Then the file should contain a "## User Request" section
And this section should appear after the "System Information" header
And the user message should be wrapped in a smart fenced codeblock (e.g., ~~~~~~text)
```

### Scenario 2: Commented lines in context files are ignored (Poka-Yoke)
> As a user, if I manually add a comment to a `.context` file, I want the system to ignore that line so that it doesn't break validation or context gathering.
```gherkin
Given a context file containing a commented line "# path/to/ignored.py"
When the system reads this context file (via Repository or Adapter)
Then the commented line should be completely ignored
And "path/to/ignored.py" should NOT be considered "in context"
```

### Scenario 3: Context leakage prevention on failed actions
> As a user, I want only successful READ actions to update the session context so that my context doesn't become polluted with "guessed" files or failed attempts.
```gherkin
Given a plan with a "READ" action for "some_file.py"
And the action fails (either via validation error OR execution failure)
When the plan is executed in a session and transitions to the next turn
Then "some_file.py" should NOT be present in the next turn's "turn.context"
```

### Scenario 4: Pruning redundant Resource Contents in session reports
> As a user in a session, I want the execution report to be concise by omitting file contents that are already in the `input.md` file.
```gherkin
Given I am executing a plan in Session Mode
When the execution report is generated
Then the "Resource Contents" section should be omitted from the report (as they are already present in input.md)
But successful "READ" actions should still be logged in the "Action Log"
```

## Deliverables
- [x] **Contract** - Add `is_session` field to `ExecutionReport` domain model.
- [x] **Contract** - Update `IExecutionReportAssembler` to accept `is_session` (or extract from Plan).
- [x] **Contract** - Update `IMarkdownReportFormatter` signature to handle session context.
- [x] **Harness** - Add regression tests in `tests/suites/unit/core/services/test_session_service.py` to verify that `turn.context` only grows on `SUCCESS` logs.
- [ ] **Logic** - Update `SessionRepository.read_context_file` to filter lines starting with `#` (Poka-Yoke for manual edits).
- [x] **Logic** - Refactor `SessionService._apply_execution_effects` to iterate over `ExecutionReport.action_logs` and only apply `READ`/`PRUNE` effects if `log.status == SUCCESS`.
- [ ] **Wiring** - Update `PlanningService.generate_plan` to inject the `## User Request` block into the `input.md` content.
- [ ] **Wiring** - Update `ExecutionReportAssembler` to propagate `is_session` to the report.
- [ ] **Wiring** - Update `MarkdownReportFormatter` to pass `is_session` flag to the Jinja2 template.
- [ ] **Cleanup** - Update `execution_report.md.j2` to conditionally hide `Resource Contents` based on the `is_session` flag.

## Delta Analysis
1.  `src/teddy_executor/core/services/planning_service.py`: Needs to modify the `full_context` construction in `generate_plan`.
2.  `src/teddy_executor/core/services/session_repository.py`: Needs to update `read_context_file` to strip lines starting with `#`.
3.  `src/teddy_executor/core/services/session_service.py`: Needs to refactor `_apply_execution_effects` to use `action_logs` instead of `original_actions`.
4.  `src/teddy_executor/core/services/markdown_report_formatter.py`: Needs to detect session mode (likely by checking for presence of `plan_path` or an explicit flag) and pass it to Jinja.
5.  `src/teddy_executor/core/services/templates/execution_report.md.j2`: Wrap the `Resource Contents` rendering block in an `{% if not is_session %}` guard.

## Implementation Notes
### Context Leakage Prevention
- Refactored `SessionService._apply_execution_effects` to use `ExecutionReport.action_logs` instead of `original_actions`.
- Verified that side effects (READ/PRUNE) are only applied if `log.status == ActionStatus.SUCCESS`.
- Added unit tests in `tests/suites/unit/core/services/test_session_service.py` covering success, failure, and skip scenarios.
