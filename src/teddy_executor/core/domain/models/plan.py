from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Sequence


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


class ExecutionStatus(str, Enum):
    """Represents the possible execution states of an action."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    SKIPPED = "SKIPPED"


@dataclass
class ActionData:
    """Represents a single action from the plan."""

    type: str
    params: dict[str, Any]
    description: str | None = None
    selected: bool = True
    modified: bool = False
    executed: bool = False
    state: ExecutionStatus = ExecutionStatus.PENDING
    user_response: Optional[str] = None
    node: Any = None
    similarity_score: float | None = None
    similarity_scores: list[float] | None = None

    @property
    def is_terminal(self) -> bool:
        """Returns True if the action is a terminal action (PROMPT, INVOKE, RETURN)."""
        return self.type in (ActionType.PROMPT, ActionType.INVOKE, ActionType.RETURN)


@dataclass(frozen=True)
class ValidationError:
    """Represents a structured validation error."""

    message: str
    action_index: int = 0
    file_path: str | None = None
    offending_node: Any = None


DEFAULT_SIMILARITY_THRESHOLD = 0.95


@dataclass
class Plan:
    """Represents a parsed and validated execution plan."""

    title: str
    rationale: str
    actions: Sequence[ActionData]
    metadata: dict[str, str] = field(default_factory=dict)
    source_doc: Any = None
    is_session: bool = False
    plan_path: str | None = None
    raw_content: str | None = None

    def __post_init__(self):
        assert self.actions, "Plan must contain at least one action."
