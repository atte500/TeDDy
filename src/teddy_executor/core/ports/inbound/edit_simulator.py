from typing import List, Protocol, TypedDict


class EditPair(TypedDict, total=False):
    find: str
    replace: str
    replace_all: bool


class IEditSimulator(Protocol):
    """
    Service for applying a sequence of FIND/REPLACE edits to a string.
    """

    def simulate_edits(
        self,
        content: str,
        edits: List[EditPair],
        threshold: float = 0.96,
        replace_all: bool = False,
    ) -> tuple[str, list[float]]:
        """
        Applies each FIND/REPLACE pair in sequence to the provided content.

        :param content: The original string content.
        :param edits: A list of EditPair dictionaries.
        :param threshold: The similarity threshold for fuzzy matching.
        :param replace_all: Global override for bulk replacement.
        :return: A tuple of (transformed_string, list_of_similarity_scores).
        :raises ValueError: If a FIND block is not found or is ambiguous (matches multiple times).
        """
        ...
