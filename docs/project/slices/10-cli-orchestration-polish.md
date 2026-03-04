# Vertical Slice: CLI Orchestration Polish (Control Flow)

## Business Goal
Streamline the non-interactive CLI experience by automatically handling context-management actions (PRUNE) and providing clear manual handoff instructions for control-flow actions (INVOKE, RETURN), while reducing report noise.

## Acceptance Criteria

### Scenario 1: PRUNE in Non-Interactive Mode
**Given** a plan containing a `PRUNE` action
**When** the plan is executed with `teddy execute --yes` (non-interactive)
**Then** the `PRUNE` action must be automatically marked as `SKIPPED`
**And** the skip reason in the report must be: "Skipped: PRUNE is not supported in manual execution mode."

### Scenario 2: INVOKE/RETURN (Mandatory Interruption)
**Given** a plan containing an `INVOKE` or `RETURN` action
**When** the plan is executed (even with `--yes` flag)
**Then** the executor must **always** interrupt and prompt the user for manual confirmation
**And** the output to the user must be a formatted instruction block requesting approval
**And** the action status in the final report must be `SUCCESS` (if approved) or `FAILURE` (if rejected).

### Scenario 3: Report Noise Reduction for Handoffs
**Given** a successfully executed `INVOKE` or `RETURN` action
**When** the execution report is generated
**Then** the report must **NOT** include the `Message` content of the action
**And** it must only display the `Action Type`, `Status`, `Target Agent` (for INVOKE), and `Handoff Resources`.

## User Showcase
1. Create a plan file containing a `PRUNE` action and an `INVOKE` action.
2. Run `poetry run teddy execute [PLAN_FILE] --yes`.
3. Observe that the `PRUNE` action is skipped without user intervention.
4. Observe that the CLI prints a "HANDOFF REQUEST" block for the `INVOKE` action and waits for input.
5. Check the generated report (clipboard or file) and verify the handoff message is omitted.

## Architectural Changes
- **`ExecutionOrchestrator`**: Update the execution loop to detect non-interactive mode and apply the auto-skip/re-route logic.
- **`MarkdownReportFormatter`**: Update the `execution_report.md.j2` template to conditionally hide message bodies for handoff actions.

## Scope of Work
- [✅] **Acceptance Test**: Create `tests/acceptance/test_non_interactive_orchestration.py` to drive out these scenarios.
- [✅] **Refactor Orchestrator**: Implement the auto-skip logic for `PRUNE` in non-interactive mode.
- [✅] **Refactor Orchestrator**: Implement the "Manual Handoff" prompt logic for `INVOKE` and `RETURN`.
- [✅] **Update Template**: Modify `src/teddy_executor/core/services/templates/execution_report.md.j2` to hide message contents for handoffs.
- [✅] **Verify**: Ensure the Concise Report (CLI) and Session Report (File) both respect the noise reduction.

## Implementation Summary
The vertical slice successfully polished the CLI orchestration for control-flow actions. Key accomplishments:
- **PRUNE Auto-Skip:** Implemented logic in `ExecutionOrchestrator` to automatically skip `PRUNE` actions when `--yes` is used, as context is not persistent in manual mode.
- **Mandatory Handoff Interruption:** Refactored `INVOKE` and `RETURN` to always interrupt the execution flow, even with the `--yes` flag. This ensures a human always confirms the transition of responsibility between agents.
- **Specialized Handoff UI:** Added `confirm_manual_handoff` to `IUserInteractor` and implemented a high-visibility instruction block in `ConsoleInteractor`.
- **Report Noise Reduction:** Updated the `execution_report.md.j2` template to suppress the `Message` body for successful handoff actions, keeping reports clean.
- **Refactoring:** Consolidated handoff parsing logic into `parse_handoff_body` and cleaned up fixture resolution in integration tests.

[NEW]: The `confirm_manual_handoff` logic currently outputs to `stderr` to avoid polluting the piped output, which is consistent with other interactive prompts.
