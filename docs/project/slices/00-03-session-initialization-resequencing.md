# Slice: Session Initialization Re-sequencing

- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Specs:** [interactive-session-workflow](../specs/interactive-session-workflow.md)

## Business Goal
Eliminate the creation of temporary "session-auto" directories by prompting the user for their instruction upfront and using it to generate a professional, slugified session name before the directory is ever created on disk.

## Scenarios
> As a user, when I start a session without a name or message, I want to be prompted for my goal immediately so that the session folder can be named correctly from the start.

```gherkin
Given no session name or message is provided
When I run "teddy start"
Then I should be prompted for "What are we working on?"
And if I enter "Refactor auth service"
Then the session folder should be created as ".teddy/sessions/YYYYMMDD_HHMMSS-refactor-auth-service"
And the planning phase should begin with that message.
```

## Deliverables
- [x] Logic - Update `handle_new_session` to prompt for message and slugify the session name.
- [x] Cleanup - Remove redundant "session-auto" placeholder and `SessionPlanner._handle_dynamic_rename` logic.

## Delta Analysis
- **Modify:** `src/teddy_executor/adapters/inbound/session_cli_handlers.py` to move the prompt and name resolution earlier in `handle_new_session`.
- **Modify:** `src/teddy_executor/core/services/session_planner.py` to remove `_handle_dynamic_rename` and its call in `trigger_new_plan`.

## Guidelines for Implementation
- Use `IUserInteractor.ask_text` (or equivalent) for the upfront prompt.
- Use `slugify` from `teddy_executor.core.utils.string`.
- Ensure the timestamp prefix is still added by `SessionService.create_session`.
- The `orchestrator.resume` call should receive the resolved message to prevent a second prompt.

## Implementation Notes
- [x] Orientation: Created vertical slice and verified `IUserInteractor` contract.
- [x] Logic: Re-sequenced `handle_new_session` to prompt for message and slugify name before disk creation.
- [x] Cleanup: Removed redundant `_handle_dynamic_rename` from `SessionPlanner`.
- [x] Integration: Updated acceptance and telemetry tests to reflect prompt-based naming convention and `slugify` stopword behavior. Ensured `-m` is used in non-interactive tests to maintain deterministic naming.
