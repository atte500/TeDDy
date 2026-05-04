# Slice: Session Telemetry UX Enhancements
- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Specs:** [interactive-session-workflow.md](../specs/interactive-session-workflow.md)

## Business Goal
Improve the transparency of AI interactions by providing real-time telemetry about model context usage *before* waiting for a response. This allows users to immediately see how close they are to context limits and confirms the system is active.

## Scenarios

> As a user in an interactive session, I want to see my context usage relative to the model's limit before the LLM starts generating, so I can anticipate context-window issues.
```gherkin
Feature: Pre-response Session Telemetry

  Scenario: Displaying full telemetry before LLM call
    Given a session with a model having a "128000" token limit
    And a cumulative session cost of "0.0500"
    And a prompt that tokenizes to "1200" tokens
    When I trigger a new plan
    Then the telemetry block should be displayed before the "Waiting for agent" message
    And the telemetry should show "• Context: 1.2k / 128.0k tokens"
    And the telemetry should show "• Session Cost: $0.0500"
```

## Deliverables
- [ ] **Contract** - Add `get_context_window(model: Optional[str] = None) -> int` to `ILlmClient`.
- [ ] **Harness** - Update `MockLlmClient` to support `get_context_window`.
- [ ] **Logic** - Implement `get_context_window` in `LiteLLMAdapter` using `litellm.get_max_tokens`.
- [ ] **Logic** - Relocate and unify telemetry display logic into `PlanningService.generate_plan`.
- [ ] **Wiring** - Display Model, Context (x/y tokens), and Session Cost (cumulative) *before* `get_completion`.
- [ ] **Cleanup** - Remove `_display_planning_telemetry` and its call site from `SessionPlanner`.

## Delta Analysis
- `src/teddy_executor/core/ports/outbound/llm_client.py`: Add new abstract method.
- `src/teddy_executor/adapters/outbound/litellm_adapter.py`: Implement `get_context_window` using `litellm.get_max_tokens(model)`.
- `src/teddy_executor/core/services/planning_service.py`:
    - Fetch context window via `llm_client`.
    - Extract `cumulative_cost` from the `meta` dict provided by `PromptManager`.
    - Print full telemetry block using `user_interactor.display_message`.
- `src/teddy_executor/core/services/session_planner.py`: Remove redundant `_display_planning_telemetry` logic.

## Guidelines for Implementation
- Use `litellm.get_max_tokens(model)` in the adapter. Handle potential `None` or exceptions by returning a sensible default (e.g., 0).
- Formatting:
    - `• Model: [magenta]{model}[/magenta]`
    - `• Context: [magenta]{used/1000:.1f}k / {total/1000:.1f}k tokens[/magenta]`
    - `• Session Cost: [magenta]${cumulative:.4f}[/magenta]`
- The `PlanningService` already gets `meta` via `self._prompt_manager.resolve_agent_metadata(turn_path)`. Use the `cumulative_cost` found there for the pre-response display.
