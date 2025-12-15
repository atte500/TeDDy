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
class ReadAction(Action):
    """Represents an action to read a file or URL."""

    source: str
    action_type: str = field(default="read", init=False)

    def __post_init__(self):
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("'source' parameter cannot be empty")

    def is_remote(self) -> bool:
        """Checks if the source is a remote URL."""
        return self.source.lower().startswith(("http://", "https://"))


@dataclass(frozen=True)
class EditAction(Action):
    """Represents an 'edit' action."""

    file_path: str
    find: str
    replace: str
    action_type: str = field(default="edit", init=False)

    def __post_init__(self):
        # Type checks
        if not isinstance(self.file_path, str):
            raise TypeError("'file_path' must be a string")
        if not isinstance(self.find, str):
            raise TypeError("'find' must be a string")
        if not isinstance(self.replace, str):
            raise TypeError("'replace' must be a string")

        # Value checks
        if not self.file_path.strip():
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


class SearchTextNotFoundError(ValueError):
    """Custom exception raised when the search text is not found during an edit operation."""

    def __init__(self, message: str, content: str):
        super().__init__(message)
        self.content = content
