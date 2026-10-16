# Component Design: PlanningService
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/services/planning_service.py`](/src/teddy_executor/core/services/planning_service.py)

## Purpose
Implements the `IPlanningUseCase` inbound port. It gathers project context, resolves the agent system prompt, calls the LLM, and persists the generated plan to the turn directory, following a pure context model with no injected instructions.

## Consumers
- [`SessionPlanner`](./session_planner.md): Calls `generate_plan` to start a turn's planning phase.
- [`SessionLifecycleManager`](/src/teddy_executor/core/services/session_lifecycle_manager.py): Consumes the planning use case through the session ports bundle.
- [CLI Adapter](../../adapters/inbound/cli.md): Drives planning for the interactive and manual flows.
- [Composition Root](/src/teddy_executor/container.py): Registers `PlanningService` and binds it to `IPlanningUseCase`.

## Dependencies
- [`IGetContextUseCase`](../ports/inbound/get_context_use_case.md): Gathers the project context payload.
- [`ILlmClient`](../ports/outbound/llm_client.md): Requests completions, token counts, and costs.
- [`IFileSystemManager`](../ports/outbound/file_system_manager.md): Writes `input.md` and `plan.md`.
- [`IConfigService`](../ports/outbound/config_service.md): Resolves model and retry settings.
- [`IPromptManager`](/src/teddy_executor/core/ports/outbound/prompt_manager.py): Resolves the agent prompt and persists telemetry.
- [`IUserInteractor`](../ports/outbound/user_interactor.md): Displays telemetry and retry notices.
- [`ISessionManager`](../ports/outbound/session_manager.md): Resolves session and turn context manifests.

## Class Invariants
- `pure_context_model`: The service never injects user instructions into the LLM `messages` or `input.md`.
- `single_gather_per_turn`: Project context is gathered exactly once and threaded to the caller.
- `retry_on_empty`: An empty LLM response is retried up to `llm.max_retries` times.
- `cost_accumulation`: Every billed attempt accumulates into the turn cost.
- `primitive_serialization`: All metadata is cast to primitive types before serialization.
- `preflight_once`: The local preflight check runs once per process via a class-level flag.
- `budget_guard`: A request that strictly exceeds the model context window raises before the LLM call.

## Inbound Ports
- **`IPlanningUseCase`**: Exposes `generate_plan(...)`.

## Outbound Ports
None declared directly — the service consumes the ports bundled in `PlanningPorts`, listed under Dependencies.

## Data Contracts
- **`PlanningPorts`** (`teddy_executor.core.domain.models.planning_ports`): The injected DTO bundling context, LLM, file system, config, prompts, user interactor, and session manager.
- **`ProjectContext`** (`teddy_executor.core.domain.models.project_context`): The gathered context returned to the caller.
- **Return tuple:** `(plan_path, turn_cost, project_context)`.

## Operations

### `generate_plan(user_message, turn_dir, context_files=None) -> tuple[str, float, ProjectContext]`
- **Preconditions:** `turn_dir` exists; the agent prompt file exists in the turn directory.
- **Postconditions:** Writes `plan.md` and `input.md`, updates `meta.yaml` telemetry, and returns the plan path, the turn cost, and the gathered `ProjectContext`.
- **Exceptions:** `ConfigurationError` when configuration is invalid or the request exceeds the context window; `FileNotFoundError` when the system prompt is missing.

### `_check_context_budget(token_count, model) -> None`
- **Preconditions:** `token_count` is the assembled request token count; `model` is the resolved model.
- **Postconditions:** Returns normally when the context window is unknown or the request fits; the guardrail never calls the LLM.
- **Exceptions:** `ConfigurationError` when the window is positive and the request strictly exceeds it.
