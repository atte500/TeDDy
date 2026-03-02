from typing import List

from teddy_executor.core.domain.models import (
    MultipleMatchesFoundError,
    SearchTextNotFoundError,
)
from teddy_executor.core.ports.inbound.edit_simulator import EditPair, IEditSimulator


class EditSimulator(IEditSimulator):
    """
    Implements IEditSimulator by applying surgical edits to a string.
    """

    def _apply_single_edit(self, content: str, find: str, replace: str) -> str:
        """
        Applies a single find/replace operation to content with domain logic.
        """
        count = content.count(find)
        if count == 0:
            raise SearchTextNotFoundError(
                message=f"Search text {find!r} not found in file.",
                content=content,
            )
        if count > 1:
            raise MultipleMatchesFoundError(
                message=f"Found {count} occurrences of {find!r}. Aborting edit to prevent ambiguity.",
                content=content,
            )

        if replace == "":
            # Newline cleanup logic to prevent orphaned empty lines
            if find + "\n" in content:
                return content.replace(find + "\n", "", 1)
            if "\n" + find in content:
                return content.replace("\n" + find, "", 1)

        return content.replace(find, replace, 1)

    def simulate_edits(self, content: str, edits: List[EditPair]) -> str:
        """
        Applies each FIND/REPLACE pair in sequence.
        """
        current_content = content

        for edit in edits:
            current_content = self._apply_single_edit(
                current_content, edit["find"], edit["replace"]
            )

        return current_content
