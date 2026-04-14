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
        match_all: bool = False,
    ) -> tuple[str, float]:
        """
        Applies a single find/replace operation to content with domain logic.
        """
        best_match, score, is_ambiguous, offset = find_best_match(
            content, find, threshold
        )

        if is_ambiguous and not match_all:
            count = content.count(find) if score == 1.0 else 2
            hint = " Please provide a larger FIND block to uniquely identify the section, refactor the code to avoid duplication. Alternatively you can use `Match All: true` to change all occurrences in the file at once."
            raise MultipleMatchesFoundError(
                message=f"Found {count} ambiguous occurrences of {find!r}. Aborting edit to prevent ambiguity.{hint}",
                content=content,
            )

        if score < threshold:
            raise SearchTextNotFoundError(
                message=f"Search text {find!r} not found in file (Best Score: {score:.2f}, Threshold: {threshold:.2f}).",
                content=content,
            )

        # Apply indentation offset to the replacement block
        if offset != 0:
            replace = self._apply_indent_offset(replace, offset)

        # Align replacement newline with original match to prevent concatenation
        final_replace = replace
        if (
            best_match.endswith("\n")
            and not find.endswith("\n")
            and not replace.endswith("\n")
            and replace != ""
        ):
            # Detect original line ending to prevent "Git Noise"
            terminator = "\r\n" if best_match.endswith("\r\n") else "\n"
            final_replace += terminator

        if replace == "" and not match_all:
            # Newline cleanup logic for surgical deletions
            if best_match.endswith("\n") and (best_match) in content:
                return content.replace(best_match, "", 1), score
            if "\n" + best_match in content:
                return content.replace("\n" + best_match, "", 1), score

        if match_all:
            # Replaces all occurrences of the found block
            return content.replace(best_match, final_replace), score
        return content.replace(best_match, final_replace, 1), score

    def _apply_indent_offset(self, replace_block: str, offset: int) -> str:
        """Applies a constant indentation offset to every non-empty line."""
        lines = replace_block.splitlines(keepends=True)
        result = []
        for line in lines:
            stripped = line.lstrip()
            if not stripped:
                result.append(line)
            elif offset > 0:
                result.append(" " * offset + line)
            elif offset < 0:
                current_indent = len(line) - len(stripped)
                to_remove = min(abs(offset), current_indent)
                result.append(line[to_remove:])
            else:
                result.append(line)
        return "".join(result)

    def simulate_edits(
        self,
        content: str,
        edits: List[EditPair],
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        match_all: bool = False,
    ) -> tuple[str, list[float]]:
        """
        Applies each FIND/REPLACE pair in sequence.
        """
        current_content = content
        all_scores = []

        for edit in edits:
            # Local match_all override from action params or global
            do_match_all = edit.get("match_all", match_all)

            if do_match_all:
                current_content, score = self._apply_single_edit(
                    current_content,
                    edit["find"],
                    edit["replace"],
                    threshold,
                    match_all=True,
                )
                all_scores.append(score)
            else:
                current_content, score = self._apply_single_edit(
                    current_content,
                    edit["find"],
                    edit["replace"],
                    threshold,
                    match_all=False,
                )
                all_scores.append(score)

        return current_content, all_scores
