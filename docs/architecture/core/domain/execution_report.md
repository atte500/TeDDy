# Component Design: ExecutionReport
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/domain/models/execution_report.py`](/src/teddy_executor/core/domain/models/execution_report.py)

## Purpose
Defines the strongly-typed, immutable data structures that report the outcome of a plan execution. It replaces legacy dictionary-based reporting and guarantees type safety across the execution and reporting layers.

## Consumers
- [`ExecutionOrchestrator`](../services/execution_orchestrator.md): Produces the `ExecutionReport` after running a plan.
- [`IExecutionReportAssembler`](../ports/outbound/execution_report_assembler.md): Assembles a report from raw execution outcome data.
- [`IMarkdownReportFormatter`](../ports/outbound/markdown_report_formatter.md): Renders the report into Markdown.
- [`ISessionManager`](../ports/outbound/session_manager.md): Persists the report to the turn directory.
- [`IRunPlanUseCase`](../ports/inbound/run_plan_use_case.md): Returns the report to the CLI boundary.
- [`SessionOrchestrator`](../services/session_orchestrator.md): Feeds report outcomes into the turn transition algorithm.
- [CLI Adapter](../../adapters/inbound/cli.md): Formats and prints the report.

## Dependencies
- **`ActionData`** (`core.domain.models.plan`): Provides the element type for the `original_actions` field.

## Class Invariants
- `frozen_dataclasses`: `ActionLog`, `RunSummary`, and `ExecutionReport` are frozen; instances are immutable after construction.
- `status_consistency`: `RunSummary.status` is a `RunStatus`; each `ActionLog.status` is an `ActionStatus`.
- `default_factory_collections`: `metadata`, `original_actions`, and `action_logs` default to empty collections.

## Inbound Ports
None — this is a passive data structure.

## Outbound Ports
None — this is a passive data structure.

## Data Contracts
- **`RunStatus`** (str Enum): `SUCCESS`, `FAILURE`, `VALIDATION_FAILED`, `SKIPPED`, `ABORTED`, `INTERRUPTED`.
- **`ActionStatus`** (str Enum): `SUCCESS`, `FAILURE`, `SKIPPED`, `PENDING`, `INTERRUPTED`.
- **`ActionLog`** (frozen dataclass): `status: ActionStatus`, `action_type: str`, `params: dict[str, Any]`, `details: Any | None`, `modified: bool`, `modified_fields: list[str]`, `failed_command: str | None`.
- **`RunSummary`** (frozen dataclass): `status: RunStatus`, `start_time: datetime`, `end_time: datetime`, `error: str | None`.
- **`ExecutionReport`** (frozen dataclass): `run_summary: RunSummary`, `plan_title: str | None`, `rationale: str | None`, `user_request: str | None`, `is_session: bool`, `metadata: dict[str, str]`, `original_actions: Sequence[ActionData]`, `action_logs: Sequence[ActionLog]`, `validation_result: Sequence[str] | None`, `validation_ast: str | None`, `failed_resources: dict[str, str] | None`.

## Operations
None — this component holds data only.
