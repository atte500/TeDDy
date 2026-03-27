# MRE: Invalid Action Type Causes Malformed Report

- **Status:** Unresolved

## 1. Failure Context
When the `teddy execute` command is run against a plan containing an unknown action type (e.g., `SYNTHESIS`), the execution correctly fails. However, the resulting execution report is malformed: it does not mark the invalid action with a `[✗]` in the AST tree, nor does it display the specific error message, hindering debugging efforts.

## 2. Steps to Reproduce
1. Create a Markdown plan file containing a syntactically correct but semantically invalid action. For example:
   ```markdown
   # Plan
   ## Action Plan
   ### `FOOBAR`
   - **Description:** An invalid action.
   ```
2. Execute the plan using `poetry run teddy execute <plan_file>`.

## 3. Expected vs. Actual Behavior
### Expected Behavior
The generated execution report should clearly indicate the failure at the action level. The AST view should mark the action with a failure symbol, and the action log should contain a clear error message.
```text
Execution Report
...
- [✓] Plan
  - [✗] Action: FOOBAR
...
Action Log:
...
[FOOBAR]
  - Status: FAILED
  - Error: Unknown action type: FOOBAR
...
```

### Actual Behavior
The report is generated, but the AST does not mark the invalid action as failed, and no error message is associated with it in the action log, making it difficult to identify the source of the failure from the report alone.

## 4. Relevant Code
- `src/teddy_executor/core/services/markdown_plan_parser.py`
- `src/teddy_executor/core/services/execution_orchestrator.py`
- `src/teddy_executor/core/services/markdown_report_formatter.py`
- `src/teddy_executor/core/domain/models/execution_report.py`

## 5. Investigation Log
- **2026-03-27:** Initial triage. Created MRE and reproduction script.
- **2026-03-27:** **Hypothesis Falsified.** A spike to bypass the `ExecutionOrchestrator`'s pre-flight validation `InvalidPlanError` still resulted in a generic validation report. This proves the root cause is not in the orchestrator but higher up in the call stack. The CLI's main exception handler appears to be generating a report without passing down the detailed validation context.

## 6. Root Cause Analysis
The root cause was identified in `src/teddy_executor/core/services/markdown_plan_parser.py` within the `_parse_actions` method. When the parser encountered a Heading (Level 3) that did not match a known action type (e.g., `FOOBAR`), it raised an `InvalidPlanError` with only a string message.

Because the `offending_nodes` parameter was omitted from the exception, the reporting mechanism (responsible for generating the "Actual Response Structure" AST) defaulted all nodes to success `[✓]`. This caused the report to be misleading, as it showed a green checkmark next to the very action that caused the parsing failure.

## 7. Implementation Notes
- **Fix:** Modified `MarkdownPlanParser._parse_actions` to pass the `action_heading` node as part of the `offending_nodes` list when raising an `InvalidPlanError` for unknown action types.
- **Verification:** Added a new acceptance test `test_unknown_action_error_shows_ast` in `tests/suites/acceptance/test_all_validation_errors_show_ast.py` which construction a plan with a `NON_EXISTENT_ACTION` and asserts that `[✗]` appears in the resulting report.
- **Cleanup:** Fixed duplication in the `tests/suites/acceptance/test_all_validation_errors_show_ast.py` file discovered during triage.

## 8. Pivot History
### 2026-03-27: Falsified Theory (Logical Validation)
**Hypothesis:** The bug originated in the `SessionOrchestrator`'s handling of logical validation errors (`PlanValidator`).
**Evidence:** Instrumentation in `ExecutionOrchestrator` showed it was never reached.
**Result:** Falsified. Direct patching and TDD testing in `SessionOrchestrator` failed to resolve the issue, suggesting the `InvalidPlanError` originates earlier in the pipeline (during parsing).
*Pending Investigation*
