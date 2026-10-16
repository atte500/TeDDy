# Component Design: IExecutionReportAssembler
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/ports/outbound/execution_report_assembler.py`](/src/teddy_executor/core/ports/outbound/execution_report_assembler.py)

## Purpose
Defines the outbound port for constructing a final `ExecutionReport` and determining the overall run status from the data collected during a plan execution. It removes report-assembly logic from the orchestrator.

## Consumers
- [`ExecutionOrchestrator`](../../services/execution_orchestrator.md): Assembles the report at the end of every run.

## Dependencies
- **`ExecutionReport`** and **`ReportAssemblyData`** (`teddy_executor.core.domain.models`): The output model and the input DTO.

## Class Invariants
- `abstract_base_class`: The port is an `ABC`; implementations override `assemble`.

## Inbound Ports
None — this is an outbound (driven) port.

## Outbound Ports
- **`IExecutionReportAssembler`**: The driven contract consumed by the orchestrator and implemented by the `ExecutionReportAssembler` service.

## Data Contracts
- **`ReportAssemblyData`** (`teddy_executor.core.domain.models.report_assembly_data`): Input DTO carrying the plan, action logs, timing, and validation outcome.

## Operations

### `assemble(data) -> ExecutionReport`
- **Preconditions:** `data` is a valid `ReportAssemblyData`.
- **Postconditions:** Returns a fully populated `ExecutionReport` with a computed `RunStatus`.
