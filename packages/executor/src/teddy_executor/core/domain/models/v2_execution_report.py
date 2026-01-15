from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Sequence


@dataclass(frozen=True)
class V2_ActionLog:
    """Logs the result of a single action execution."""

    status: Literal["SUCCESS", "FAILURE", "SKIPPED", "PENDING"]
    action_type: str
    params: dict[str, Any]
    details: str | None = None


# Placeholder for a more complete domain model to be defined elsewhere.
@dataclass(frozen=True)
class V2_TeddyProject:
    """Represents the project context for an execution."""

    name: str = "unknown"


@dataclass(frozen=True)
class V2_RunSummary:
    """Summarizes the overall result of a plan execution."""

    status: Literal["SUCCESS", "FAILURE", "SKIPPED"]
    start_time: datetime
    end_time: datetime
    project: V2_TeddyProject
    error: str | None = None


@dataclass(frozen=True)
class V2_ExecutionReport:
    """The comprehensive report of a plan execution."""

    run_summary: V2_RunSummary
    action_logs: Sequence[V2_ActionLog] = field(default_factory=list)
