from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Sequence

from teddy_executor.core.domain.models import ActionLog, ExecutionReport, Plan


class IExecutionReportAssembler(ABC):
    """
    Defines the outbound port for assembling an ExecutionReport and determining run status.
    """

    @abstractmethod
    def assemble(
        self,
        plan: Plan,
        action_logs: Sequence[ActionLog],
        start_time: datetime,
        _message: Optional[str] = None,
    ) -> ExecutionReport:
        """
        Calculates the final run status and constructs a complete ExecutionReport.
        """
        raise NotImplementedError
