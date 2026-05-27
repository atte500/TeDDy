from abc import ABC, abstractmethod

from teddy_executor.core.domain.models import ExecutionReport, ReportAssemblyData


class IExecutionReportAssembler(ABC):
    """
    Defines the outbound port for assembling an ExecutionReport and determining run status.
    """

    @abstractmethod
    def assemble(
        self,
        data: ReportAssemblyData,
    ) -> ExecutionReport:
        """
        Calculates the final run status and constructs a complete ExecutionReport.
        """
        raise NotImplementedError
