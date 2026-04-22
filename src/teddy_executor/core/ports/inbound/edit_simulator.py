from typing import List, Protocol, TypedDict
from teddy_executor.core.domain.models.plan import DEFAULT_SIMILARITY_THRESHOLD


class EditPair(TypedDict, total=False):
    find: str
    replace: str
    match_all: bool


class IEditSimulator(Protocol):
    """
    Service for applying a sequence of FIND/REPLACE edits to a string.
    """

    def simulate_edits(
        self,
        content: str,
        edits: List[EditPair],
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        match_all: bool = False,
    ) -> tuple[str, list[float]]:
        """
        Applies each FIND/REPLACE pair in sequence to the provided content.

        :param content: The original string content.
        :param edits: A list of EditPair dictionaries.
        :param threshold: The similarity threshold for fuzzy matching.
        :param match_all: Global override for bulk replacement.
        :return: A tuple of (transformed_string, list_of_similarity_scores).
        :raises ValueError: If a FIND block is not found or is ambiguous (matches multiple times).
        """
        ...
