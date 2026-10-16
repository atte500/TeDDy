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
- [`ActionExecutor`](/src/teddy_executor/core/services/action_executor.py): Confirms and dispatches each action.
- [`IFileSystemManager`](../ports/outbound/file_system_manager.md): Reads plan files and writes temporary plans.
- [`IExecutionReportAssembler`](../ports/outbound/execution_report_assembler.md): Builds the final report.
- [`IUserInteractor`](../ports/outbound/user_interactor.md): Displays messages.
- [`IPlanReviewer`](../ports/inbound/plan_reviewer.md): Optional interactive review.
- [`InterruptGuard`](/src/teddy_executor/core/utils/interrupt_guard.py): Optional two-phase Ctrl+C drain.

## Class Invariants
- `stateless_execution`: The service holds no session history and no knowledge of future turns.
- `ports_via_dto`: Every collaborator arrives through the `OrchestratorPorts` DTO; the service holds no container reference.
- `halt_on_failure`: A `FAILURE` action without `allow_failure` halts the remaining actions.
- `communication_turn_bypass`: A communication turn bypasses the reviewer and step-by-step confirmation.
- `interrupt_drain`: When the interrupt guard is set, every remaining action is skipped with the interrupt reason and the loop exits normally.
- `temp_plan_cleanup`: A generated temporary plan file is removed in a `finally` block.

## Inbound Ports
- **`IRunPlanUseCase`**: Exposes `execute(...)`; `resume(...)` raises `NotImplementedError` because sessions are not supported here.

## Outbound Ports
None declared directly — the service consumes the concrete services and ports bundled in `OrchestratorPorts`, listed under Dependencies.

## Data Contracts
- **`OrchestratorPorts`** (`teddy_executor.core.domain.models.orchestrator_ports`): The injected DTO bundling the parser, validator, action executor, file system, report assembler, user interactor, optional reviewer, and optional interrupt guard.
- **`Plan`** and **`ExecutionReport`** (`teddy_executor.core.domain.models`): The executed object and its result.
- **`ReportAssemblyData`** (`teddy_executor.core.domain.models.report_assembly_data`): The input DTO for report assembly.

## Operations

### `execute(plan=None, plan_content=None, plan_path=None, interactive=True, message=None, project_context=None, pipeline=False) -> ExecutionReport`
- **Preconditions:** Exactly one of `plan`, `plan_content`, or `plan_path` supplies the plan.
- **Postconditions:** Returns the assembled `ExecutionReport`. The method resolves the plan, validates it, performs the interactive review, dispatches the actions, and assembles the report. A user abort returns an `ABORTED` report.
- **Exceptions:** `InvalidPlanError` when validation fails; `ValueError` when no plan source is provided.

### `resume(session_name, interactive=True, project_context=None) -> tuple[str, Optional[ExecutionReport]]`
- **Preconditions:** None.
- **Postconditions:** None — session resumption is not supported by this service.
- **Exceptions:** `NotImplementedError` always.
