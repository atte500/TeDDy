from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional, Sequence

if TYPE_CHECKING:
    from teddy_executor.core.domain.models.execution_report import ActionLog


class ActionType(str, Enum):
    CREATE = "CREATE"
    READ = "READ"
    EDIT = "EDIT"
    EXECUTE = "EXECUTE"
    RESEARCH = "RESEARCH"
    MOVE = "MOVE"
    DELETE = "DELETE"
    MESSAGE = "MESSAGE"


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
    modified_fields: list[str] = field(default_factory=list)
    executed: bool = False
    state: ExecutionStatus = ExecutionStatus.PENDING
    action_log: Optional[ActionLog] = None
    user_response: Optional[str] = None
    pending_temp_file: Optional[str] = None
    node: Any = None
    similarity_score: float | None = None
    similarity_scores: list[float] | None = None
    # Recorded when the action is resolved (dispatched or skipped), never at
    # parse, so the console log and the report can both order by it.
    execution_sequence: int | None = None

    @property
    def is_terminal(self) -> bool:
        """Returns True if the action is a communication action."""
        return self.type == ActionType.MESSAGE


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

    def is_communication_turn(self) -> bool:
        """Returns True if the plan consists only of a MESSAGE action."""
        return len(self.actions) == 1 and self.actions[0].type == ActionType.MESSAGE

    def next_execution_sequence(self) -> int:
        """Returns the sequence number the next resolved action must record.

        The number follows the highest recorded stamp rather than the count of
        recorded stamps, so a plan whose actions were partly executed by hand
        continues after them instead of reusing their numbers.
        """
        recorded = [
            action.execution_sequence
            for action in self.actions
            if action.execution_sequence is not None
        ]
        return max(recorded) + 1 if recorded else 1
