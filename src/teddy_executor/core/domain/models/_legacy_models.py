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
    cwd: Optional[str] = None
    env: Optional[Dict[str, str]] = None
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
class ChatWithUserAction(Action):
    """Represents a 'chat_with_user' action."""

    prompt: str
    action_type: str = field(default="chat_with_user", init=False)

    def __post_init__(self):
        if not isinstance(self.prompt, str):
            raise TypeError("'prompt' must be a string")
        if not self.prompt.strip():
            raise ValueError("'prompt' parameter cannot be empty")


@dataclass(frozen=True)
class ResearchAction(Action):
    """Represents a 'research' action."""

    queries: List[str]
    action_type: str = field(default="research", init=False)

    def __post_init__(self):
        if not isinstance(self.queries, list):
            raise TypeError("'queries' must be a list")
        if not self.queries:
            raise ValueError("'queries' must be a non-empty list")
        if not all(isinstance(q, str) for q in self.queries):
            raise ValueError("All items in 'queries' must be strings")


@dataclass(frozen=True)
class ActionResult:
    """Represents the outcome of a single action's execution."""

    action: Action
    status: str
    output: Optional[str] = None
    error: Optional[str] = None
    reason: Optional[str] = None

    def __post_init__(self):
        valid_statuses = {"SUCCESS", "FAILURE", "COMPLETED", "SKIPPED"}
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
class SearchResult:
    """Represents a single search result item."""

    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class QueryResult:
    """Represents the collection of results for a single search query."""

    query: str
    search_results: List[SearchResult]


@dataclass(frozen=True)
class SERPReport:
    """Represents the aggregated results for all queries in a ResearchAction."""

    results: List[QueryResult]


@dataclass(frozen=True)
class ContextResult:
    """
    Aggregates all information gathered by the context command.
    This is a data transfer object (DTO) that structures the data for the CLI formatter.
    """

    system_info: Dict[str, str]
    repo_tree: str
    context_vault_paths: List[str]
    file_contents: Dict[str, Optional[str]]


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


class FileAlreadyExistsError(FileExistsError):
    """Custom exception raised when trying to create a file that already exists."""

    def __init__(self, message: str, file_path: str):
        super().__init__(message)
        self.file_path = file_path


class MultipleMatchesFoundError(Exception):
    """Custom exception for when an edit operation finds multiple matches."""

    def __init__(self, message: str, content: str):
        super().__init__(message)
        self.content = content


class WebSearchError(Exception):
    """Custom exception raised when a web search operation fails."""

    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        super().__init__(message)
        self.original_exception = original_exception
