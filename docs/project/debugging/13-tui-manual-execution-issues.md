# Bug: TUI Manual Execution Issues

- **Status:** Unresolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
1. **Missing PROMPT Response:** When a `PROMPT` action is manually executed using 'x', the final execution report says "Response captured.", but the user response is not shown in the report itself.
2. **TUI Stutter:** When an action is manually executed, the TUI stutters/flicks off and then on again when execution is finished.

**MRE:** `[Pending]`

## Diagnostic Analysis

### Causal Model
- **Manual Execution (x):** The TUI triggers `execute_step_logic` as an exclusive background worker, which calls `orchestrate_execution`.
- **PROMPT Response Loss:** `orchestrate_execution` (or its helpers) likely creates a dummy `ActionLog` with `details="Response captured."` instead of preserving the dictionary returned by the dispatcher/interactor. This prevents the Jinja template (which checks for `log.details.get('response')`) from displaying the response.
- **Stutter:** The TUI background worker executes the dispatcher (and thus the interactor's blocking input) without calling `app.suspend()`. This causes the TUI and the prompt to battle for the terminal's state.

### Discrepancies
- Final report contains "Response captured." but no content for `PROMPT` actions. [RESOLVED]
- TUI visually bugs out (corrupts) when manual execution of an action finishes. [RESOLVED]
- TUI bindings (Footer) do not refresh immediately after 'x' completion. [RESOLVED]
- 'd' (View Details) opens an empty file instead of the formatted action log. [RESOLVED]
- 'q' binding is labeled "Cancel" instead of "Quit".
- Final execution report discards manually executed actions if the plan is aborted/quit.

### Investigation History
- [2026-04-15] Initial report and context gathering. `grep` for `key="x"` failed, widening search.
- [2026-04-15] MRE unit script failed multiple times due to domain model schema mismatches (`ActionData` and `ActionLog`). The core fix in `ExecutionOrchestrator` and `ReviewerApp` has been applied, but the verification needs to be moved to a formal test using the actual `PlanBuilder` and `TestEnvironment`.
- [2026-04-15] The formal test failed because `ExecutionOrchestrator` retrieved from `env.get_service` did not have the `mock_plan_reviewer` injected, causing it to bypass the interactive review phase entirely.
