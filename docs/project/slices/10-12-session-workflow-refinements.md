# Slice: Session Workflow Refinements
- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](/docs/project/milestones/10-interactive-session-and-config.md)
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:** N/A

## Business Goal
As a user of the interactive session (`teddy start`), I want a smooth and silent workflow that allows the agent to complete its tasks without re-prompting me for instructions at every step, and without cluttering my console with redundant information or reports, so that I can have an efficient and focused development experience.

## Scenarios

### Scenario: Agent completes a multi-step task without re-prompting
> As a user, I want to give an initial instruction and have the agent execute its multi-step plan without asking me for new instructions between steps, so that the workflow is continuous.

```gherkin
Given a new teddy session has been started with the initial instruction "Create a file named 'test.txt' with the content 'hello', then read the file back to me."
When the agent executes the `CREATE` action for 'test.txt'
And I approve the action
Then the system should NOT prompt me for new instructions
And the agent should proceed to execute the `READ` action for 'test.txt'
And I approve the action
Then the session should conclude or await further agent actions without re-prompting me for instructions.
```

### Scenario: Console output is clean and minimal
> As a user, I want the console output during a session to be free of redundant information, so I can focus on the agent's actions and my decisions.

```gherkin
Given a teddy session is in progress
When the agent generates a plan
Then the console output should NOT contain raw, unformatted "Tokens:" or "Cost:" lines
And the console output should NOT contain a "Planning Turn with..." header message
When the agent completes an action and a report is generated
Then the full execution report content should NOT be printed to the console
```

## Deliverables
- [ ] Refactor - Modify the `while` loop in `src/teddy_executor/adapters/inbound/session_cli_handlers.py` to correctly manage the session state, ensuring it does not re-prompt for user input after every agent plan execution.
- [ ] Refactor - Modify the `handle_report_output` function (likely in `src/teddy_executor/adapters/inbound/cli_helpers.py`) to prevent the execution report content from being printed to the console in interactive session mode. It should still be written to file and copied to the clipboard.
- [ ] Refactor - Remove the direct `display_message` or `sys.stdout.write` calls for "Tokens:" and "Cost:" from `src/teddy_executor/core/services/prompt_manager.py`.
- [ ] Refactor - Remove the `display_message` call that prints the "[NN] Planning Turn with..." header from `src/teddy_executor/core/services/session_planner.py` and `src/teddy_executor/core/services/session_lifecycle_manager.py`.

## Delta Analysis
- `src/teddy_executor/adapters/inbound/session_cli_handlers.py`: The main session loop will be refactored to be state-aware, rather than a simple `while True`.
- `src/teddy_executor/adapters/inbound/cli_helpers.py`: The report handling function will be modified to conditionally suppress output.
- `src/teddy_executor/core/services/prompt_manager.py`: Redundant print statements will be removed.
- `src/teddy_executor/core/services/session_planner.py`: Redundant print statements will be removed.
- `src/teddy_executor/core/services/session_lifecycle_manager.py`: Redundant print statements will be removed.

## Guidelines for Implementation
- The key change is to the session loop. The loop should only prompt for a new "User Request" when the agent explicitly yields control back to the user via a `RETURN` action or a similar state change, not after every single plan execution.
- Ensure the changes do not break non-interactive (`--no-interactive`) session execution.
- Verify that the final, formatted telemetry message (e.g., "• Session Cost: $0.0249") is still displayed, while the raw, preceding lines are removed.
