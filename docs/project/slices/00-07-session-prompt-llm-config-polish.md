# Slice 00-07: Session Prompt & LLM Config Polish

- **Status:** Planned
- **Milestone:** [09-interactive-session-and-config](../milestones/09-interactive-session-and-config.md)
- **Specs:** [interactive-session-workflow](../specs/interactive-session-workflow.md)

## 1. Business Goal
Restore the integrity of the configuration system by ensuring user-defined LLM settings are honored and providing a professional, flexible UX for initial session instructions.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Configuration Priority
The `LiteLLMAdapter` must prioritize values found in the `ConfigService` over any hardcoded defaults or call-time arguments provided by internal services.
#### Deliverables
- [ ] Refactor `LiteLLMAdapter.get_completion` to merge configuration values with higher priority than internal defaults.
- [ ] Unit test verifying that if `api_key` or `model` is in the config, it is passed to `litellm.completion` even if a different default is suggested by the caller.

### Scenario 2: Decoupled Planning
The `PlanningService` must not hardcode a specific model string (e.g., "gpt-4o").
#### Deliverables
- [ ] Update `PlanningService` to retrieve the `model` from `ConfigService`.
- [ ] Ensure a safe fallback mechanism if no model is configured (e.g., logging a warning or using a default constant).

### Scenario 3: Initial Prompt UX Alignment
The "Enter your instructions for the AI" prompt in the `new` session workflow must support the same multi-line/editor capabilities as the `PROMPT` action.
#### Deliverables
- [ ] Update `SessionOrchestrator._trigger_new_plan` to use `self._user_interactor.ask_question` instead of `self._user_interactor.prompt`.
- [ ] Verify that typing 'e' at the initial prompt opens the external editor.

## 3. Architectural Changes
- **PlanningService:** Inject `IConfigService` and remove hardcoded strings.
- **LiteLLMAdapter:** Refine dictionary merging logic in `get_completion`.
- **SessionOrchestrator:** Switch method call for user input gathering.
