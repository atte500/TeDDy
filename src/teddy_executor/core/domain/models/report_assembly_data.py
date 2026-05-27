from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence

from teddy_executor.core.domain.models import ActionLog, Plan


@dataclass(frozen=True)
class ReportAssemblyData:
    """
    DTO grouping parameters for ExecutionReport assembly.
    """

    plan: Plan
    action_logs: Sequence[ActionLog]
    start_time: datetime
    message: Optional[str] = None
    is_session: bool = False
