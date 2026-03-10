from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence


class ActionType(str, Enum):
    CREATE = "CREATE"
    READ = "READ"
    EDIT = "EDIT"
    EXECUTE = "EXECUTE"
    RESEARCH = "RESEARCH"
    PROMPT = "PROMPT"
    PRUNE = "PRUNE"
    INVOKE = "INVOKE"
    RETURN = "RETURN"


@dataclass
class ActionData:
    """Represents a single action from the plan."""

    type: str
    params: dict[str, Any]
    description: str | None = None
    selected: bool = True
    modified: bool = False


@dataclass(frozen=True)
class ValidationError:
    """Represents a structured validation error."""

    message: str
    action_index: int = 0
    file_path: str | None = None


@dataclass
class Plan:
    """Represents a parsed and validated execution plan."""

    title: str
    rationale: str
    actions: Sequence[ActionData]
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.actions:
            raise ValueError("Plan must contain at least one action.")
