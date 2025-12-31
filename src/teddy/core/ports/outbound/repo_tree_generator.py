from typing import Protocol


class IRepoTreeGenerator(Protocol):
    """
    Outbound Port for generating a repository file tree.
    """

    def generate_tree(self) -> str:
        """
        Generates a string representation of the file tree,
        respecting rules from .gitignore.

        Returns:
            str: The file tree as a multi-line string.
        """
        ...
