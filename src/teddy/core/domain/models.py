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

        if self.action_type == "execute":
            if "command" not in self.params:
                raise ValueError("'execute' action requires a 'command' parameter")

            command = self.params["command"]
            if not isinstance(command, str) or not command.strip():
                raise ValueError("'command' parameter cannot be empty")


@dataclass(frozen=True)
class ActionResult:
    """Represents the outcome of a single action's execution."""

    action: Action
    status: str
    output: Optional[str]
    error: Optional[str]

    def __post_init__(self):
        valid_statuses = {"SUCCESS", "FAILURE"}
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
