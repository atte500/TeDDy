from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectContext:
    """
    A strictly-typed DTO representing the aggregated project context for display.

    Attributes:
        header: A string containing metadata about the context (e.g., CWD, OS).
        content: A string containing the main body of the context (e.g., file tree and file contents).
    """

    header: str
    content: str
