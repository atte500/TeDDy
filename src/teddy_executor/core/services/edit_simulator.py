from typing import List

from teddy_executor.core.domain.models import (
    MultipleMatchesFoundError,
    SearchTextNotFoundError,
)
from teddy_executor.core.domain.models.plan import DEFAULT_SIMILARITY_THRESHOLD
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
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        replace_all: bool = False,
    ) -> tuple[str, float]:
        """
        Applies a single find/replace operation to content with domain logic.
        """
        best_match, score, is_ambiguous = find_best_match(content, find, threshold)

        if is_ambiguous and not replace_all:
            count = content.count(find) if score == 1.0 else 2
            hint = " Please provide a larger FIND block to uniquely identify the section, refactor the code to avoid duplication, and to use Replace All: true if intention is to change all occurrences in the file."
            raise MultipleMatchesFoundError(
                message=f"Found {count} ambiguous occurrences of {find!r}. Aborting edit to prevent ambiguity.{hint}",
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

        if replace == "" and not replace_all:
            # Newline cleanup logic for surgical deletions
            if best_match.endswith("\n") and (best_match) in content:
                return content.replace(best_match, "", 1), score
            if "\n" + best_match in content:
                return content.replace("\n" + best_match, "", 1), score

        if replace_all:
            # Replaces all occurrences of the found block
            return content.replace(best_match, final_replace), score
        return content.replace(best_match, final_replace, 1), score

    def simulate_edits(
        self,
        content: str,
        edits: List[EditPair],
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        replace_all: bool = False,
    ) -> tuple[str, list[float]]:
        """
        Applies each FIND/REPLACE pair in sequence.
        """
        current_content = content
        all_scores = []

        for edit in edits:
            # Local replace_all override from action params or global
            do_replace_all = edit.get("replace_all", replace_all)

            if do_replace_all:
                current_content, score = self._apply_single_edit(
                    current_content,
                    edit["find"],
                    edit["replace"],
                    threshold,
                    replace_all=True,
                )
                all_scores.append(score)
            else:
                current_content, score = self._apply_single_edit(
                    current_content,
                    edit["find"],
                    edit["replace"],
                    threshold,
                    replace_all=False,
                )
                all_scores.append(score)

        return current_content, all_scores
