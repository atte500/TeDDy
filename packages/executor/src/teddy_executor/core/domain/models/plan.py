from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class ActionData:
    """Represents a single action from the plan."""

    type: str
    params: dict[str, Any]


@dataclass(frozen=True)
class Plan:
    """Represents a parsed and validated execution plan."""

    actions: Sequence[ActionData]

    def __post_init__(self):
        if not self.actions:
            raise ValueError("Plan must contain at least one action.")
