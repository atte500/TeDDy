from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass(frozen=True)
class Action:
    """Represents a single step in a plan."""

    action_type: str = field(init=False)


@dataclass(frozen=True)
class ExecuteAction(Action):
    """Represents an 'execute' action."""

    command: str
    action_type: str = field(default="execute", init=False)

    def __post_init__(self):
        if not isinstance(self.command, str) or not self.command.strip():
            raise ValueError("'command' parameter cannot be empty")


@dataclass(frozen=True)
class ParsePlanAction(Action):
    """A synthetic action to represent plan parsing in reports."""

    action_type: str = field(default="parse_plan", init=False)


@dataclass(frozen=True)
class CreateFileAction(Action):
    """Represents a 'create_file' action."""

    file_path: str
    content: str = ""
    action_type: str = field(default="create_file", init=False)

    def __post_init__(self):
        if not isinstance(self.file_path, str) or not self.file_path.strip():
            raise ValueError("'file_path' parameter cannot be empty")


@dataclass(frozen=True)
class ActionResult:
    """Represents the outcome of a single action's execution."""

    action: Action
    status: str
    output: Optional[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        valid_statuses = {"SUCCESS", "FAILURE", "COMPLETED"}
        if self.status not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")


@dataclass(frozen=True)
class Plan:
    """Represents a full plan to be executed, containing a list of actions."""

    actions: List[Action]

    def __post_init__(self):
        if not self.actions:
            raise ValueError("Plan must contain at least one action")


@dataclass(frozen=True)
class CommandResult:
    """Represents the captured result of an external command."""

    stdout: str
    stderr: str
    return_code: int


@dataclass
class ExecutionReport:
    """A comprehensive report detailing the execution of an entire Plan."""

    run_summary: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, Any] = field(default_factory=dict)
    action_logs: List[ActionResult] = field(default_factory=list)
