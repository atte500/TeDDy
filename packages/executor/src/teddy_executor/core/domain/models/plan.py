from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class ActionData:
    """Represents a single action from the plan."""

    type: str
    params: dict[str, Any]


@dataclass(frozen=True)
class V2_Plan:
    """Represents a parsed and validated execution plan."""

    actions: Sequence[ActionData]
