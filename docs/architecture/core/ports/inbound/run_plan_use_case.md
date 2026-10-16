# Component Design: IRunPlanUseCase
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/ports/inbound/run_plan_use_case.py`](/src/teddy_executor/core/ports/inbound/run_plan_use_case.py)

## Purpose
Defines the primary inbound port that all driving adapters use to execute a plan and to resume a session. It orchestrates parsing, execution, and report generation. The port is implemented by the `ExecutionOrchestrator`.

## Consumers
- [CLI Adapter](../../../adapters/inbound/cli.md): Drives the `execute` and session `resume` flows.

## Dependencies
- **`Plan`** and **`ExecutionReport`** (`teddy_executor.core.domain.models`): The executed object and its result.
- **`ProjectContext`** (`teddy_executor.core.domain.models.project_context`): Optional execution context.

## Class Invariants
- `abstract_base_class`: The port is an `ABC`; implementations must override every abstract operation.

## Inbound Ports
- **`IRunPlanUseCase`**: Exposes `execute(...)` and `resume(...)`.

## Outbound Ports
None — the port declares no injected dependencies.

## Data Contracts
- **`Plan`**, **`ExecutionReport`**, and **`ProjectContext`**: Domain models exchanged by the execution flow.

## Operations

### `execute(plan=None, plan_content=None, plan_path=None, interactive=True, message=None, project_context=None, pipeline=False) -> ExecutionReport`
- **Preconditions:** Exactly one of `plan`, `plan_content`, or `plan_path` supplies the plan.
- **Postconditions:** Returns the `ExecutionReport` for the run.

### `resume(session_name, interactive=True, project_context=None) -> tuple[str, Optional[ExecutionReport]]`
- **Preconditions:** `session_name` identifies an existing session.
- **Postconditions:** Returns `(actual_session_name, report)`. The turn may execute under a renamed session, though a session keeps one folder for its lifetime.
