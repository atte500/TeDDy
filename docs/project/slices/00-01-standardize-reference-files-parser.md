# Vertical Slice: Standardize "Reference Files" Parser and Reporting

## Business Goal
Align the `teddy` execution engine with the new agent communication standards as defined in [docs/project/specs/plan-format.md](/docs/project/specs/plan-format.md) and [docs/project/specs/plan-format-validation.md](/docs/project/specs/plan-format-validation.md). The parser must now recognize "Reference Files" instead of "Handoff Resources" for `INVOKE` and `RETURN` actions, and the `PROMPT` action must be extended to support this resource list.

## Acceptance Criteria
- **Scenario 1: Parser recognizes "Reference Files" in INVOKE/RETURN**
  - GIVEN a plan with an `INVOKE` or `RETURN` action using the header `- **Reference Files:** (Optional)`
  - WHEN the plan is parsed
  - THEN the resources are correctly extracted into the action's parameters.

- **Scenario 2: Parser treats PROMPT as free-form**
  - GIVEN a plan with a `PROMPT` action
  - WHEN the plan is parsed
  - THEN the entire content under the heading is captured as a single message string.

- **Scenario 3: CLI and Reports use "Reference Files" naming**
  - GIVEN a successful execution of an action with resources
  - WHEN the CLI output or Execution Report is generated
  - THEN the header displayed is "Reference Files", not "Handoff Resources".

## User Showcase
1. Create a plan with a `PROMPT` action including a `Reference Files` list.
2. Run `teddy execute` on the plan.
3. Verify that the CLI prompt shows "Reference Files".
4. Verify that the generated Execution Report (clipboard) uses the "Reference Files" header.

## Architectural Changes
- **Core (Services/Domain):**
  - Update `parser_metadata.py` to match "Reference Files:".
  - Update `action_parser_strategies.py` for `PROMPT` to parse metadata before the message.
  - Update `execution_orchestrator.py` to use the new parameter naming.
- **Adapters/Infrastructure:**
  - Update `console_interactor.py` for CLI display.
  - Update `execution_report.md.j2` for report generation.

## Deliverables
- [✓] Updated `parser_metadata.py` to recognize "Reference Files".
- [✓] Updated `PROMPT` strategy to support metadata lists.
- [✓] Updated `execution_orchestrator.py` parameter mapping.
- [✓] Updated `console_interactor.py` UI labels.
- [✓] Updated `execution_report.md.j2` template.
- [✓] Unit tests for new parsing logic in `test_markdown_plan_parser.py`.
- [✓] Acceptance test for full "Reference Files" flow in `test_prompt_action.py`.

## Implementation Summary
The vertical slice has been successfully implemented and verified.
- **Parser Standardization:** `parser_metadata.py` now recognizes both legacy "Handoff Resources" and new "Reference Files" keys.
- **PROMPT Enhancement:** The `PROMPT` action now supports structured metadata lists, allowing agents to provide reference files alongside free-form messages.
- **UI/UX Refinement:** All user-facing labels in the CLI and Execution Reports have been standardized to "Reference Files".
- **Refactoring:** `ActionFactory` was refactored to reduce cyclomatic complexity (resolving a C901 violation). The test suite was balanced to maintain the test pyramid (Acceptance < Integration < Unit).
- **Verification:** 2 new acceptance tests, 3 new unit tests, and 1 new integration test were added.
