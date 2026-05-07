from dataclasses import dataclass


from typing import Dict, List, Optional


from dataclasses import field


@dataclass
class ContextItem:
    """
    Metadata for a single context file.

    Attributes:
        path: The relative file path.
        token_count: Estimated token size.
        git_status: 2-char git status code.
        scope: Source scope (System/Session/Turn).
        selected: Whether the file is selected for the next turn.
        auto_prune_reason: Reason for pre-deselection, if any.
    """

    path: str
    token_count: int
    git_status: str
    scope: str
    selected: bool = True
    auto_prune_reason: Optional[str] = None


@dataclass(frozen=True)
class ProjectContext:
    """
    A strictly-typed DTO representing the aggregated project context for display.

    Attributes:
        header: A string containing metadata about the context (e.g., CWD, OS).
        content: The main body of the context (e.g., file tree and contents).
        scoped_paths: A mapping of scope names (e.g., 'Turn', 'Session') to lists of file paths.
        git_status: An optional string containing the output of 'git status -s'.
        items: Structured list of context files and metadata.
        agent_name: Name of the active agent.
        system_prompt_tokens: Token count of the system prompt.
        total_window: Total context window for the model.
    """

    header: str
    content: str
    scoped_paths: Dict[str, List[str]] = field(default_factory=dict)
    git_status: Optional[str] = None
    items: List[ContextItem] = field(default_factory=list)
    agent_name: str = "Unknown"
    system_prompt_tokens: int = 0
    total_window: int = 0
