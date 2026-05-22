# Slice: Minimize Metadata Footprint
- **Status:** Planned
- **Milestone:** [/docs/project/milestones/10-interactive-session-and-config.md](/docs/project/milestones/10-interactive-session-and-config.md)
- **Specs:** [/docs/project/specs/interactive-session-workflow.md](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** N/A
- **Showcase:** N/A
- **Component Docs:** [/docs/architecture/core/services/session_service.md](/docs/architecture/core/services/session_service.md), [/docs/architecture/core/services/planning_service.md](/docs/architecture/core/services/planning_service.md)

## Business Goal
Simplify the stateful session directory structure by stripping away redundant, over-engineered machine-readable metadata fields (such as `user_request`, `is_replan`, `turn_id`, `parent_turn_id`, `caller_turn_id`, and `finish_reason`) from `meta.yaml`. Retain only the necessary keys required for telemetry and startup: `creation_timestamp`, `turn_cost`, `cumulative_cost`, `token_count`, `model`, and `agent_name`.

## Scenarios
> As a developer using stateful session turns, I want my turn metadata to contain only essential telemetry and bootstrap keys, so that the session directory is clean and free of redundant, over-engineered tracking fields.

```gherkin
Scenario: Stateful turn bootstrap contains only minimal metadata
  Given a new session "feat-auth" is created for agent "pathfinder"
  Then the metadata for turn "01" should contain "creation_timestamp"
  And the metadata for turn "01" should have "agent_name" set to "pathfinder"
  And the metadata for turn "01" should have "cumulative_cost" set to 0.0
  And the metadata for turn "01" should not contain "user_request"
  And the metadata for turn "01" should not contain "turn_id"

Scenario: Post-planning updates preserve essential telemetry and discard finish_reason
  Given an active session turn directory "01"
  When the planning service completes planning for turn "01"
  Then the metadata for turn "01" should be updated with "turn_cost", "token_count", and "model"
  And the metadata for turn "01" should not contain "finish_reason"
  And the metadata for turn "01" should not contain "user_request"

Scenario: Turn transition carries forward cumulative cost and timestamps sequentially
  Given a completed turn "01" with "cumulative_cost" set to 0.00150
  When the system transitions to the next turn "02" with a turn cost of 0.00120
  Then the metadata for turn "02" should be created in the "02" directory
  And the metadata for turn "02" should have "cumulative_cost" set to 0.00270
  And the metadata for turn "02" should have "agent_name" set to the current agent
  And the metadata for turn "02" should not contain "parent_turn_id"
  And the metadata for turn "02" should not contain "is_replan"
```

## Edge Cases
- **[Parent Key Absence]**: If the parent metadata has no `cumulative_cost` field or it is malformed, then the transitioned turn should fall back to initializing `cumulative_cost` strictly as `turn_cost`, in order to prevent NaN errors or telemetry corruption.
- **[Zero Tokens Telemetry]**: If a turn fails or generates an empty response where `token_count` is 0, then the metadata must still record `token_count: 0` and `turn_cost: 0.0`, in order to maintain structural consistency for external reporting tools.

## Deliverables
Checklist of atomic units of work ordered following the Deliverable Dependency Sequence:

- [ ] **Logic** - Edit `SessionService.create_session` to write only `turn_id`'s replacement metadata: `creation_timestamp`, `agent_name`, and `cumulative_cost: 0.0` to `meta.yaml`, completely omitting `turn_id`.
- [ ] **Logic** - Edit `SessionService._persist_next_meta` to write only `creation_timestamp`, `agent_name`, `turn_cost`, and `cumulative_cost` to the next turn's `meta.yaml`, completely omitting `parent_turn_id` and `is_replan` fields.
- [ ] **Logic** - Clean up `PlanningService.generate_plan` to remove any references to `user_request` or `is_replan` when resolving or updating metadata.
- [ ] **Logic** - Clean up `PromptManager.update_meta` to completely remove the writing of `finish_reason` to `meta.yaml`.
- [ ] **Wiring** - Update standard session and orchestrator integration test assertions (e.g., in `tests/suites/integration/core/services/test_session_orchestration_integration.py` and `test_session_orchestrator_validation.py`) to stop asserting on `parent_turn_id`, `is_replan`, and other removed fields.
- [ ] **Refactor** - Clean up or remove unit tests explicitly validating removed metadata-preservation rules (e.g., in `tests/suites/unit/core/services/test_planning_service.py` and `test_session_service_transition.py`).

## Implementation Notes
*This section will be populated by the Developer as changes are implemented.*

## Implementation Plan
1. **Prune redundant writing in `SessionService`**: Modify `create_session` and `_persist_next_meta` to write only the minimal schema. Ensure no calculations crash if parent fields are missing (Edge Case).
2. **Prune `PlanningService` metadata lookups**: Remove `is_replan` checks and standard prompt preservation code, as user request history is no longer tracked in `meta.yaml`.
3. **Prune `PromptManager` diagnostics**: Remove `finish_reason` serialization in `update_meta`.
4. **Update Test Assertions**: Search and replace any test cases in `tests/` asserting on `turn_id`, `parent_turn_id`, `is_replan`, or `finish_reason` within `meta.yaml` dictionaries. Delete tests explicitly dedicated to validating these deprecated features to keep the test suite green and maintain high quality standards.
