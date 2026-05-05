# Slice: Session Telemetry UX Enhancements
- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Specs:** [interactive-session-workflow.md](../specs/interactive-session-workflow.md)
- **Prototype:** [prototypes/00-03/telemetry_prototype.py](/prototypes/00-03/telemetry_prototype.py)
- **Showcase:** [prototypes/00-03/showcase.sh](/prototypes/00-03/showcase.sh)

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
    Then the "Waiting for agent" message should be displayed
    And the telemetry block should follow immediately
    And the telemetry should show "• Model: gpt-4o"
    And the telemetry should show "• Context: 1.2k / 128.0k tokens"
    And the telemetry should show "• Session Cost: $0.0500"
```

## Deliverables
- [x] **Contract (Expansion)** - Add `get_context_window(model: Optional[str] = None) -> int` to `ILlmClient` with default return.
- [x] **Harness** - Update `MockLlmClient` in `tests/harness/setup/mocks.py` to support `get_context_window`.
- [x] **Logic (Migration)** - Implement `get_context_window` in `LiteLLMAdapter` using `litellm.model_cost`.
- [x] **Contract (Contraction)** - Make `get_context_window` abstract in `ILlmClient`.
- [x] **Logic** - Add telemetry display logic to `PlanningService.generate_plan`.
- [x] **Migration** - Update `SessionPlanner.trigger_new_plan` to no longer call telemetry display.
- [x] **Cleanup** - Remove `SessionPlanner._display_planning_telemetry` and related dead code.
- [ ] **Wiring** - Verify end-to-end telemetry display in interactive session.

## Delta Analysis
- **Port:** `src/teddy_executor/core/ports/outbound/llm_client.py`: Add `get_context_window(model: Optional[str] = None) -> int`.
- **Adapter:** `src/teddy_executor/adapters/outbound/litellm_adapter.py`: Implement using `litellm.model_cost`. Logic: Try `max_input_tokens`, then `max_tokens`, then 0.
- **Service:** `src/teddy_executor/core/services/planning_service.py`:
    - Relocate telemetry logic from `SessionPlanner`.
    - Insertion point: Immediately after `token_count = self._llm_client.get_token_count(...)` and before the retry loop.
    - Retrieval: Fetch `cumulative_cost` from `meta` provided by `self._prompt_manager.resolve_agent_metadata`.
- **Service:** `src/teddy_executor/core/services/session_planner.py`:
    - Delete `_display_planning_telemetry`.
    - Update `trigger_new_plan` to no longer call it.
- **Contract Verification:** Prototyping confirmed `max_input_tokens` is the correct field for the 128k context window on GPT-4o.

## Guidelines for Implementation
- Use `litellm.model_cost.get(model, {}).get("max_input_tokens")` in the adapter to retrieve the true context window. Fall back to `max_tokens` (output limit) if unavailable.
- Telemetry block MUST appear *after* the status line.
- Formatting:
    - `• Model: [magenta]{model}[/magenta]`
    - `• Context: [magenta]{used/1000:.1f}k / {total/1000:.1f}k tokens[/magenta]`
    - `• Session Cost: [magenta]${cumulative:.4f}[/magenta]`
- The `PlanningService` already gets `meta` via `self._prompt_manager.resolve_agent_metadata(turn_path)`. Use the `cumulative_cost` found there for the pre-response display.

## Implementation Notes
### Contract (Expansion)
- Added `get_context_window` to `ILlmClient` with a default implementation returning `0`.
- Verified with unit test `test_llm_client_provides_default_context_window` to ensure non-breaking behavior for existing adapters.

### Harness
- Updated `mock_llm_client` fixture in `tests/harness/setup/mocks.py` to return a default context window of `128000`.
- Added `tests/suites/unit/test_llm_harness.py` to verify harness defaults.

### Logic (PlanningService)
- Implemented `_display_telemetry` to provide a unified telemetry block (Model, Context, Cost).
- Added `_safe_float` utility to handle potential `MagicMock` or string leaks in telemetry calculations, ensuring the UI doesn't crash during edge cases or tests.
- Integrated telemetry display into `generate_plan` immediately after tokenization and before the LLM retry loop.
- Verified behavior with unit test `test_generate_plan_displays_telemetry_before_llm_call`.
