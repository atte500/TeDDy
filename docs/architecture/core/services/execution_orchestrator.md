# Component Design: ExecutionOrchestrator
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/services/execution_orchestrator.py`](/src/teddy_executor/core/services/execution_orchestrator.py)

## Purpose
Implements the `IRunPlanUseCase` inbound port. It runs a parsed `Plan` atomically by validating it, optionally reviewing it, dispatching each action, and assembling the final `ExecutionReport`, with no knowledge of session history.

## Consumers
- [CLI Adapter](../../adapters/inbound/cli.md): Drives the `execute` flow and session resumption through the `IRunPlanUseCase` port.
- [`SessionOrchestrator`](./session_orchestrator.md): Wraps this orchestrator for session-aware turns.
- [Composition Root](/src/teddy_executor/container.py): Registers `ExecutionOrchestrator` and binds it to `IRunPlanUseCase`.

## Dependencies
- [`IPlanParser`](../ports/inbound/plan_parser.md): Parses raw plan content into a `Plan`.
- [`IPlanValidator`](../ports/inbound/plan_validator.md): Runs pre-flight validation.
- [`ActionExecutor`](/src/teddy_executor/core/services/action_executor.py): Confirms and dispatches each action, receiving the plan-level facts this orchestrator forwards. It holds no component design doc, so its role in that pass-through is documented here and in the dispatcher's contract.
- [`IFileSystemManager`](../ports/outbound/file_system_manager.md): Reads plan files and writes temporary plans.
- [`IExecutionReportAssembler`](../ports/outbound/execution_report_assembler.md): Builds the final report.
- [`IUserInteractor`](../ports/outbound/user_interactor.md): Displays messages.
- [`IPlanReviewer`](../ports/inbound/plan_reviewer.md): Optional batch plan review.
- [`InterruptGuard`](/src/teddy_executor/core/utils/interrupt_guard.py): Optional two-phase Ctrl+C drain.

## Class Invariants
- `stateless_execution`: The service holds no session history and no knowledge of future turns.
- `ports_via_dto`: Every collaborator arrives through the `OrchestratorPorts` DTO; the service holds no container reference.
- `halt_on_failure`: A `FAILURE` action without `allow_failure` halts the remaining actions.
- `communication_turn_bypass`: A communication turn bypasses the reviewer and step-by-step confirmation.
- `interrupt_drain`: When the interrupt guard is set, every remaining action is skipped with the interrupt reason and the loop exits normally.
- `session_marker`: A session turn writes an empty `execution.started` marker into its turn directory after validation and review succeed and immediately before the first dispatch; a stateless run and an aborted review write none. The marker outlives dispatch only until the turn is finalized, which clears it once the report exists.
- `temp_plan_cleanup`: A generated temporary plan file is removed in a `finally` block.
- `session_scope_passthrough`: At dispatch time the session root is derived once from the plan's own path (`session_root_from_plan_path` in `core.utils.paths`) and forwarded with `agent_name` and `is_session` into `ActionExecutor.confirm_and_dispatch`, so a READ on a URL is built with the session's cache scope. A plan without an on-disk path has no session scope, and its actions run uncached rather than failing.

## Inbound Ports
- **`IRunPlanUseCase`**: Exposes `execute(...)`; `resume(...)` raises `NotImplementedError` because sessions are not supported here.

## Outbound Ports
None declared directly — the service consumes the concrete services and ports bundled in `OrchestratorPorts`, listed under Dependencies.

## Data Contracts
- **`OrchestratorPorts`** (`teddy_executor.core.domain.models.orchestrator_ports`): The injected DTO bundling the parser, validator, action executor, file system, report assembler, user interactor, optional reviewer, and optional interrupt guard.
- **`Plan`** and **`ExecutionReport`** (`teddy_executor.core.domain.models`): The executed object and its result.
- **`ReportAssemblyData`** (`teddy_executor.core.domain.models.report_assembly_data`): The input DTO for report assembly.
- **`InvalidPlanError`** (`teddy_executor.core.ports.inbound.plan_parser`): Raised when pre-flight plan validation fails.

## Operations

### `execute(plan=None, plan_content=None, plan_path=None, require_approval=True, message=None, project_context=None, pipeline=False) -> ExecutionReport`
- **Preconditions:** Exactly one of `plan`, `plan_content`, or `plan_path` supplies the plan.
- **Postconditions:** Returns the assembled `ExecutionReport`. The method resolves the plan, validates it, performs the batch plan review, then — for a session plan — writes an empty `execution.started` marker into the turn directory immediately before the first dispatch, dispatches the actions, and assembles the report. Every dispatch carries the session root derived from the plan's path, so an action that reads a remote resource reaches it through the session cache. A user abort returns an `ABORTED` report and writes no marker, and a plan that fails pre-flight validation raises before any marker write.
- **Exceptions:**
  - `InvalidPlanError`: Plan pre-flight validation fails.
  - `ValueError`: No plan source (`plan`, `plan_content`, or `plan_path`) provided.

### `resume(session_name, require_approval=True, project_context=None) -> tuple[str, Optional[ExecutionReport]]`
- **Preconditions:** None.
- **Postconditions:** None — session resumption is not supported by this service.
- **Exceptions:**
  - `NotImplementedError`: Session resumption is unsupported by this service.
