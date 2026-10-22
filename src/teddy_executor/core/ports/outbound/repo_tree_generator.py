from typing import Protocol


class IRepoTreeGenerator(Protocol):
    """
    Outbound Port for generating a repository file tree.
    """

    @property
    def max_depth(self) -> int:
        """The maximum directory nesting depth rendered in the tree."""
        ...

    @property
    def max_tree_width(self) -> int:
        """The maximum visible entries listed for a non-root directory."""
        ...

    def generate_tree(self) -> str:
        """
        Generates a string representation of the file tree,
        respecting rules from .gitignore.

        Returns:
            str: The file tree as a multi-line string.
        """
        ...
