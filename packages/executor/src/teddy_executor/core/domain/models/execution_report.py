from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Sequence


class RunStatus(str, Enum):
    """Overall status for an entire plan execution."""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class ActionStatus(str, Enum):
    """Status for a single action within a plan."""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    SKIPPED = "SKIPPED"
    PENDING = "PENDING"


@dataclass(frozen=True)
class ActionLog:
    """Logs the result of a single action execution."""

    status: ActionStatus
    action_type: str
    params: dict[str, Any]
    details: Any | None = None


@dataclass(frozen=True)
class RunSummary:
    """Summarizes the overall result of a plan execution."""

    status: RunStatus
    start_time: datetime
    end_time: datetime
    error: str | None = None


@dataclass(frozen=True)
class ExecutionReport:
    """The comprehensive report of a plan execution."""

    run_summary: RunSummary
    action_logs: Sequence[ActionLog] = field(default_factory=list)
