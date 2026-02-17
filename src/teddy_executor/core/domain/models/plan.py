from dataclasses import dataclass
from enum import Enum
from typing import Any, Sequence


class ActionType(str, Enum):
    CREATE = "CREATE"
    READ = "READ"
    EDIT = "EDIT"
    EXECUTE = "EXECUTE"
    RESEARCH = "RESEARCH"
    CHAT_WITH_USER = "CHAT_WITH_USER"
    PRUNE = "PRUNE"
    INVOKE = "INVOKE"
    RETURN = "RETURN"


@dataclass(frozen=True)
class ActionData:
    """Represents a single action from the plan."""

    type: str
    params: dict[str, Any]
    description: str | None = None


@dataclass(frozen=True)
class Plan:
    """Represents a parsed and validated execution plan."""

    title: str
    actions: Sequence[ActionData]

    def __post_init__(self):
        if not self.actions:
            raise ValueError("Plan must contain at least one action.")
