"""
Validation rules for the 'EDIT' action.
"""

import difflib
import os
from typing import List

from teddy_executor.core.domain.models.plan import ActionData
from teddy_executor.core.ports.outbound import IFileSystemManager
from teddy_executor.core.services.validation_rules.helpers import (
    PlanValidationError,
    ValidationError,
    validate_path_is_safe,
)
from teddy_executor.core.utils.markdown import get_fence_for_content


def _find_best_match_and_diff(file_content: str, find_block: str) -> str:
    """
    Finds the most similar block of text in the file content and generates a diff.
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
        diff = difflib.ndiff(find_lines, best_match_lines)
        return "".join(diff)

    return ""


def _validate_single_edit(
    edit: dict, content: str, file_path: str
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
                        f"{file_path}\n"
                        f"**Block Content:**\n"
                        f"{fence}\n{find_block}\n{fence}"
                    ),
                    file_path=str(file_path),
                )
            )
            return errors

        matches = content.count(find_block)
        if matches == 0:
            diff_text = _find_best_match_and_diff(content, find_block)
            fence = get_fence_for_content(find_block)
            error_msg = (
                f"The `FIND` block could not be located in the file: "
                f"{file_path}\n"
                f"**FIND Block:**\n"
                f"{fence}\n{find_block}\n{fence}\n"
            )
            if diff_text:
                diff_fence = get_fence_for_content(diff_text)
                error_msg += (
                    f"**Closest Match Diff:**\n{diff_fence}diff\n"
                    f"{diff_text}\n{diff_fence}\n"
                )
            error_msg += (
                "**Hint:** You need to match the target content "
                "exactly, including any whitespace and indentations."
            )
            errors.append(ValidationError(message=error_msg, file_path=str(file_path)))
        elif matches > 1:
            fence = get_fence_for_content(find_block)
            errors.append(
                ValidationError(
                    message=(
                        f"The `FIND` block is ambiguous. Found {matches} "
                        f"matches in: {file_path}\n"
                        f"**FIND Block:**\n"
                        f"{fence}\n{find_block}\n{fence}"
                    ),
                    file_path=str(file_path),
                )
            )
    return errors


def validate_edit_action(
    action: ActionData, file_system_manager: IFileSystemManager
) -> List[ValidationError]:
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

        if not file_system_manager.path_exists(path_str):
            raise PlanValidationError(
                f"File to edit does not exist: {path_str}",
                file_path=path_str,
            )
    except (PlanValidationError, FileNotFoundError) as e:
        # Catch FileNotFoundError in case path_exists is mocked to return True
        # but read_file fails, which can happen in some test scenarios.
        return [
            ValidationError(
                message=getattr(e, "message", str(e)),
                file_path=getattr(e, "file_path", path_str),
            )
        ]

    action_errors: List[ValidationError] = []
    content = file_system_manager.read_file(path_str)

    edits = action.params.get("edits")
    if isinstance(edits, list):
        for edit in edits:
            action_errors.extend(_validate_single_edit(edit, content, path_str))
    return action_errors
