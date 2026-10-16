# Component Design: SessionOrchestrator
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/services/session_orchestrator.py`](/src/teddy_executor/core/services/session_orchestrator.py)

## Purpose
Implements the `IRunPlanUseCase` inbound port as a decorator-style service that wraps the stateless `ExecutionOrchestrator` to add stateful session behavior. It parses and validates the turn plan, gathers and prunes context, persists the formatted report, drives turn transitions, and renders turn visibility to the terminal.

## Consumers
- [SessionLifecycleManager](/src/teddy_executor/core/services/session_lifecycle_manager.py): Drives `execute` and `resume` for every session turn.
- [CLI Adapter](../../adapters/inbound/cli.md): Starts and resumes sessions through the lifecycle funnel.
- [Composition Root](/src/teddy_executor/container.py): Constructs the orchestrator and injects its collaborators.

## Dependencies
- [`ExecutionOrchestrator`](./execution_orchestrator.md): The wrapped stateless executor that runs the plan.
- [`ISessionManager`](../ports/outbound/session_manager.md): Loads and saves turn metadata during transitions.
- [`IFileSystemManager`](../ports/outbound/file_system_manager.md): Reads the plan file and persists the report.
- [`IPlanValidator`](../ports/inbound/plan_validator.md): Runs pre-flight validation.
- [`IPlanParser`](../ports/inbound/plan_parser.md): Parses raw plan content.
- [`IUserInteractor`](../ports/outbound/user_interactor.md): Prompts the user when a plan aborts.
- [SessionLifecycleManager](/src/teddy_executor/core/services/session_lifecycle_manager.py): Owns the resume funnel, the tee guard, finalization, and replan triggers.
- [SessionReplanner](/src/teddy_executor/core/services/session_replanner.py): Builds failure reports for non-session runs.
- [`ContextService`](./context_service.md): Gathers context when the turn arrives without one.
- [`IConfigService`](../ports/outbound/config_service.md): Supplies the configured model name.
- [`ILlmClient`](../ports/outbound/llm_client.md): Reports the context window and token counts.
- [`PromptManager`](./prompt_manager.md): Resolves the system prompt for token counting.
- [`SessionPruningService`](./session_pruning_service.md): Optional. Prunes context items before harvesting.

## Class Invariants
- `tee_single_install`: The orchestrator installs the history-log tee only when `SessionLifecycleManager.tee_active` is `False`, so planning output is captured once.
- `mandatory_prune`: `prune()` runs on every session turn, on whichever context is present, and strictly before `_harvest_context`.
- `single_gather_per_turn`: A provided `project_context` is forwarded as-is; the in-execute re-gather runs only when `project_context is None`.
- `harvest_before_validation`: Pruned paths are recorded before validation so they persist across a replan.
- `history_log_never_at_root`: The tee path is redirected under `.tmp/` when it would resolve to the project root.

## Inbound Ports
- **`IRunPlanUseCase`**: Exposes `execute(...)` and `resume(...)`.

## Outbound Ports
- **`ISessionManager`**, **`IFileSystemManager`**, **`IPlanValidator`**, **`IPlanParser`**, **`IUserInteractor`**, **`IConfigService`**, **`ILlmClient`**: Consumed through their contracts; see Dependencies.

## Data Contracts
- **`ExecutionReport`** (`teddy_executor.core.domain.models.execution_report`): Produced and returned by every run.
- **`Plan`** (`teddy_executor.core.domain.models.plan`): The parsed turn plan; its `metadata` carries `Status`, `Agent`, `user_request`, and `pruned_context`.
- **`ProjectContext`** (`teddy_executor.core.domain.models.project_context`): Gathered, pruned, and harvested.

## Operations

### `execute(plan=None, plan_content=None, plan_path=None, interactive=True, message=None, project_context=None, pipeline=False) -> ExecutionReport`
- **Preconditions:** At most one of `plan`, `plan_content`, or `plan_path` supplies the plan; an empty `message` signals termination.
- **Postconditions:** Returns the `ExecutionReport` for the turn. In session mode it harvests pruned context, persists `report.md`, and finalizes the turn. A pipeline turn ending with a non-empty MESSAGE sets `awaiting_reply` and skips finalization. An empty communication reply returns `None` and prints a termination notice.
- **Exceptions:** Propagates a parse error when not in session mode; a session-mode parse error triggers a replan instead.

### `resume(session_name, interactive=True, project_context=None, pipeline=False, message=None)`
- **Preconditions:** `session_name` identifies an existing session.
- **Postconditions:** Delegates to `SessionLifecycleManager.resume`, which runs the session state machine.

### Module helpers
The module single-sources terminal rendering for session turns. `_print_initial_request` prints the initial user request and falls back to `initial_request.md`. `_print_header_bar` prints the plan status emoji and title. `_print_user_message` prints the user reply resolved from the direct message, `plan.metadata["user_request"]`, or the MESSAGE action log. `_print_message_from_teddy` prints the agent MESSAGE under the shared cyan framing, shared with the `resume -p` stop-again path.
