from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass(frozen=True)
class Action:
    """Represents a single step in a plan."""

    action_type: str
    params: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.action_type or not isinstance(self.action_type, str):
            raise ValueError("action_type must be a non-empty string")

        # "parse_plan" is a special internal action type for reporting YAML errors.
        known_action_types = {"execute", "create_file", "parse_plan"}
        if self.action_type not in known_action_types:
            raise ValueError(f"Unknown action type: '{self.action_type}'")

        if self.action_type == "execute":
            self._validate_execute_params()
        elif self.action_type == "create_file":
            self._validate_create_file_params()

    def _validate_execute_params(self):
        if "command" not in self.params:
            raise ValueError("'execute' action requires a 'command' parameter")
        command = self.params.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ValueError("'command' parameter cannot be empty")

    def _validate_create_file_params(self):
        if "file_path" not in self.params:
            raise ValueError("'create_file' action requires a 'file_path' parameter")
        file_path = self.params.get("file_path")
        if not isinstance(file_path, str) or not file_path.strip():
            raise ValueError("'file_path' parameter cannot be empty")

        if "content" not in self.params:
            self.params["content"] = ""


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
