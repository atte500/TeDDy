from typing import List, Protocol, TypedDict


class EditPair(TypedDict):
    find: str
    replace: str


class IEditSimulator(Protocol):
    """
    Service for applying a sequence of FIND/REPLACE edits to a string.
    """

    def simulate_edits(
        self, content: str, edits: List[EditPair], threshold: float = 0.95
    ) -> str:
        """
        Applies each FIND/REPLACE pair in sequence to the provided content.

        :param content: The original string content.
        :param edits: A list of EditPair dictionaries.
        :param threshold: The similarity threshold for fuzzy matching.
        :return: The transformed string.
        :raises ValueError: If a FIND block is not found or is ambiguous (matches multiple times).
        """
        ...
