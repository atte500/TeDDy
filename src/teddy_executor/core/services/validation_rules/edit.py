"""
Validation rules for the 'EDIT' action.
"""

import difflib
import os
from typing import List

from teddy_executor.core.domain.models.plan import ActionData
from teddy_executor.core.ports.outbound import IFileSystemManager
from teddy_executor.core.services.validation_rules.helpers import (
    IActionValidator,
    PlanValidationError,
    ValidationError,
    validate_path_is_safe,
)
from teddy_executor.core.utils.markdown import get_fence_for_content


class EditActionValidator(IActionValidator):
    """Validator for the 'EDIT' action."""

    def __init__(self, file_system_manager: IFileSystemManager):
        self._file_system_manager = file_system_manager

    def can_validate(self, action_type: str) -> bool:
        return action_type.lower() == "edit"

    def validate(self, action: ActionData) -> List[ValidationError]:
        """
        Validates an 'edit' action.
        """
        path_str = (
            action.params.get("path")
            or action.params.get("file_path")
            or action.params.get("File Path")
        )

        if not isinstance(path_str, str):
            return []

        try:
            validate_path_is_safe(path_str, "EDIT")

            if not self._file_system_manager.path_exists(path_str):
                raise PlanValidationError(
                    f"File to edit does not exist: {path_str}",
                    file_path=path_str,
                )
        except (PlanValidationError, FileNotFoundError) as e:
            return [
                ValidationError(
                    message=getattr(e, "message", str(e)),
                    file_path=getattr(e, "file_path", path_str),
                )
            ]

        action_errors: List[ValidationError] = []
        content = self._file_system_manager.read_file(path_str)

        edits = action.params.get("edits")
        if isinstance(edits, list):
            total_edits = len(edits)
            for i, edit in enumerate(edits, 1):
                action_errors.extend(
                    _validate_single_edit(edit, content, path_str, i, total_edits)
                )
        return action_errors


def _find_best_match(file_content: str, find_block: str) -> str:
    """
    Finds the most similar block of text in the file content.
    """
    file_lines = file_content.splitlines(keepends=True)
    find_lines = find_block.splitlines(keepends=True)
    num_find_lines = len(find_lines)

    if not file_lines or not find_lines:
        return ""

    best_ratio = 0.0
    best_match_lines: List[str] = []

    # Sliding window over the file content
    for i in range(len(file_lines) - num_find_lines + 1):
        window = file_lines[i : i + num_find_lines]
        matcher = difflib.SequenceMatcher(None, "".join(window), find_block)
        ratio = matcher.ratio()

        if ratio > best_ratio:
            best_ratio = ratio
            best_match_lines = window

    # If the file is smaller than the find block, just compare against the
    # whole file
    if len(file_lines) < num_find_lines:
        best_match_lines = file_lines

    if best_match_lines:
        return "".join(best_match_lines)

    return ""


def _validate_single_edit(
    edit: dict, content: str, file_path: str, edit_index: int, total_edits: int
) -> List[ValidationError]:
    """Validates a single edit dictionary."""
    errors: List[ValidationError] = []
    find_block = edit.get("find")
    replace_block = edit.get("replace")

    if os.environ.get("TEDDY_DEBUG"):
        print("\n--- TEDDY DEBUG: PlanValidator ---")
        print(f"File: {file_path}")
        print(f"Content (repr): {repr(content)}")
        print(f"Find Block (repr): {repr(find_block)}")
        print("--- END TEDDY DEBUG ---\n")

    if isinstance(find_block, str):
        if find_block == replace_block:
            fence = get_fence_for_content(find_block)
            errors.append(
                ValidationError(
                    message=(
                        f"FIND and REPLACE blocks are identical in: "
                        f"{file_path} (Edit Pair {edit_index} of {total_edits})\n"
                        f"**Block Content:**\n"
                        f"{fence}\n{find_block}\n{fence}"
                    ),
                    file_path=str(file_path),
                )
            )
            return errors

        matches = content.count(find_block)
        if matches == 0:
            best_match_text = _find_best_match(content, find_block)
            error_msg = (
                f"The `FIND` block could not be located in the file: "
                f"{file_path} (Edit Pair {edit_index} of {total_edits})\n"
            )
            if best_match_text:
                best_fence = get_fence_for_content(best_match_text)
                error_msg += (
                    f"**Closest Match in File:**\n"
                    f"{best_fence}\n{best_match_text}\n{best_fence}\n"
                )
            error_msg += (
                '**Hint:** Review the "Closest Match" to see the exact indentation and whitespace used in the file. '
                "Use this exact text in your next FIND block."
            )
            errors.append(ValidationError(message=error_msg, file_path=str(file_path)))
        elif matches > 1:
            fence = get_fence_for_content(find_block)
            errors.append(
                ValidationError(
                    message=(
                        f"The `FIND` block is ambiguous (Edit Pair {edit_index} of {total_edits}). "
                        f"Found {matches} matches in: {file_path}\n"
                        f"**FIND Block:**\n"
                        f"{fence}\n{find_block}\n{fence}"
                    ),
                    file_path=str(file_path),
                )
            )
    return errors


# Removed legacy functional validation rule in favor of EditActionValidator class.
