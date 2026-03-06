from dataclasses import dataclass


from typing import Dict, List


from dataclasses import field


@dataclass(frozen=True)
class ProjectContext:
    """
    A strictly-typed DTO representing the aggregated project context for display.

    Attributes:
        header: A string containing metadata about the context (e.g., CWD, OS).
        content: The main body of the context (e.g., file tree and contents).
        scoped_paths: A mapping of scope names (e.g., 'Turn', 'Session') to lists of file paths.
    """

    header: str
    content: str
    scoped_paths: Dict[str, List[str]] = field(default_factory=dict)
