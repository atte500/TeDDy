from typing import List

from teddy_executor.core.domain.models import (
    MultipleMatchesFoundError,
    SearchTextNotFoundError,
)
from teddy_executor.core.ports.inbound.edit_simulator import EditPair, IEditSimulator
from teddy_executor.core.services.validation_rules.edit_matcher import find_best_match


class EditSimulator(IEditSimulator):
    """
    Implements IEditSimulator by applying surgical edits to a string.
    """

    def _apply_single_edit(
        self,
        content: str,
        find: str,
        replace: str,
        threshold: float = 0.95,
    ) -> str:
        """
        Applies a single find/replace operation to content with domain logic.
        """
        best_match, score, is_ambiguous = find_best_match(content, find, threshold)

        if is_ambiguous:
            # We use content.count to check for exact ambiguity count if the score is 1.0,
            # but if it's fuzzy, any tie is a MultipleMatchesFoundError.
            count = content.count(find) if score == 1.0 else 2
            raise MultipleMatchesFoundError(
                message=f"Found {count} ambiguous occurrences of {find!r}. Aborting edit to prevent ambiguity.",
                content=content,
            )

        if score < threshold:
            raise SearchTextNotFoundError(
                message=f"Search text {find!r} not found in file (Best Score: {score:.2f}, Threshold: {threshold:.2f}).",
                content=content,
            )

        # Align replacement newline with original match to prevent concatenation
        final_replace = replace
        if (
            best_match.endswith("\n")
            and not find.endswith("\n")
            and not replace.endswith("\n")
            and replace != ""
        ):
            final_replace += "\n"

        if replace == "":
            # Newline cleanup logic to prevent orphaned empty lines
            if best_match.endswith("\n") and (best_match) in content:
                return content.replace(best_match, "", 1)
            if "\n" + best_match in content:
                return content.replace("\n" + best_match, "", 1)

        return content.replace(best_match, final_replace, 1)

    def simulate_edits(
        self,
        content: str,
        edits: List[EditPair],
        threshold: float = 0.95,
    ) -> str:
        """
        Applies each FIND/REPLACE pair in sequence.
        """
        current_content = content

        for edit in edits:
            current_content = self._apply_single_edit(
                current_content, edit["find"], edit["replace"], threshold
            )

        return current_content
