# Outbound Port: IExecutionReportAssembler

The `IExecutionReportAssembler` defines the contract for constructing a final `ExecutionReport` from the various pieces of data collected during a plan execution.

## 1. Design Principles

- **Separation of Concerns:** Decouples the logic of "how to build a report" (e.g., determining status, timestamps) from the orchestrator.
- **DTO Driven:** Uses the `ReportAssemblyData` DTO to maintain a clean, low-arity signature and comply with `PLR0913`.
- **Immutability:** Produces an immutable `ExecutionReport` domain model.

## 2. Port Interface

```python
from abc import ABC, abstractmethod
from teddy_executor.core.domain.models import ExecutionReport, ReportAssemblyData

class IExecutionReportAssembler(ABC):
    @abstractmethod
    def assemble(self, data: ReportAssemblyData) -> ExecutionReport:
        """
        Calculates the final run status and constructs a complete ExecutionReport.
        """
        pass
```

## 3. Implementation Details

The implementation is responsible for:
1. **Status Determination:** Determining the overall `RunStatus` (SUCCESS, FAILURE, SKIPPED) based on the hierarchy of `ActionLog` outcomes.
2. **Timing:** Calculating execution duration using the `start_time` provided in the DTO and the current system time.
3. **Data Mapping:** Aggregating data from the `Plan` (title, rationale, metadata) and `ActionLog`s into the final `ExecutionReport` structure.
