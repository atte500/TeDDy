"""
This module contains the implementation of the PlanValidator service.
"""

# Placeholder content
# The Developer will implement this based on the design document.
# See: docs/architecture/core/services/plan_validator.md

import difflib
import os
from pathlib import Path
from typing import List

from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.utils.markdown import get_fence_for_content


from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationError:
    """Represents a structured validation error."""

    message: str
    file_path: Optional[str] = None


class PlanValidationError(Exception):
    """Custom exception for plan validation errors."""

    def __init__(self, message: str, file_path: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.file_path = file_path


class PlanValidator(IPlanValidator):
    """
    Implements IPlanValidator using a strategy pattern to run pre-flight checks.
    """

    def _find_best_match_and_diff(self, file_content: str, find_block: str) -> str:
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

        # If the file is smaller than the find block, just compare against the whole file
        if len(file_lines) < num_find_lines:
            best_match_lines = file_lines

        if best_match_lines:
            diff = difflib.ndiff(find_lines, best_match_lines)
            return "".join(diff)

        return ""

    def _validate_path_is_safe(self, path_str: str, action_type: str):
        """
        Ensures a file path is safe by checking for absolute paths and
        directory traversal attempts.
        """
        if os.path.isabs(path_str):
            raise PlanValidationError(
                f"Action `{action_type}` contains an absolute path, which is not allowed: {path_str}"
            )
        if ".." in Path(path_str).parts:
            raise PlanValidationError(
                f"Action `{action_type}` contains a directory traversal attempt ('..'), which is not allowed: {path_str}"
            )

    def validate(self, plan: Plan) -> List[ValidationError]:
        """
        Validates a plan by dispatching each action to a specific validation method.

        Returns:
            A list of validation error objects. An empty list signifies success.
        """
        errors: List[ValidationError] = []
        for action in plan.actions:
            # Normalize action type to lowercase to match method names
            validator_method = getattr(
                self, f"_validate_{action.type.lower()}_action", None
            )
            if validator_method:
                action_errors = validator_method(action)
                if action_errors:
                    errors.extend(action_errors)
        return errors

    def _validate_create_action(self, action: ActionData) -> List[ValidationError]:
        """Validates a 'create' action."""
        try:
            path_str = action.params.get("path")
            if isinstance(path_str, str):
                self._validate_path_is_safe(path_str, "CREATE")
                if Path(path_str).exists():
                    raise PlanValidationError(
                        f"File already exists: {path_str}", file_path=path_str
                    )
            return []
        except PlanValidationError as e:
            return [ValidationError(message=e.message, file_path=e.file_path)]

    def _validate_read_action(self, action: ActionData) -> List[ValidationError]:
        """Validates a 'read' action."""
        try:
            path_str = action.params.get("resource")
            # URLs are not file paths and should be ignored by this validator.
            if isinstance(path_str, str) and not path_str.startswith(
                ("http://", "https://")
            ):
                self._validate_path_is_safe(path_str, "READ")
            return []
        except PlanValidationError as e:
            return [ValidationError(message=e.message, file_path=e.file_path)]

    def _validate_edit_action(self, action: ActionData) -> List[ValidationError]:
        """
        Validates an 'edit' action.
        """
        # Check for keys in various casings to handle different parser outputs
        path_str = (
            action.params.get("path")
            or action.params.get("file_path")
            or action.params.get("File Path")
        )

        if not isinstance(path_str, str):
            return []

        try:
            self._validate_path_is_safe(path_str, "EDIT")

            file_path = Path(path_str)
            if not file_path.exists():
                raise PlanValidationError(
                    f"File to edit does not exist: {file_path}",
                    file_path=str(file_path),
                )
        except PlanValidationError as e:
            return [ValidationError(message=e.message, file_path=e.file_path)]

        action_errors: List[ValidationError] = []
        content = file_path.read_text(encoding="utf-8")

        # Handle 'edits' list (from Markdown parser)
        edits = action.params.get("edits")
        if isinstance(edits, list):
            for edit in edits:
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
                        action_errors.append(
                            ValidationError(
                                message=(
                                    f"FIND and REPLACE blocks are identical in: {file_path}\n"
                                    f"**Block Content:**\n"
                                    f"{fence}\n{find_block}\n{fence}"
                                ),
                                file_path=str(file_path),
                            )
                        )
                        continue

                    matches = content.count(find_block)
                    if matches == 0:
                        diff_text = self._find_best_match_and_diff(content, find_block)
                        fence = get_fence_for_content(find_block)
                        error_msg = (
                            f"The `FIND` block could not be located in the file: {file_path}\n"
                            f"**FIND Block:**\n"
                            f"{fence}\n{find_block}\n{fence}\n"
                        )
                        if diff_text:
                            diff_fence = get_fence_for_content(diff_text)
                            error_msg += f"**Closest Match Diff:**\n{diff_fence}diff\n{diff_text}\n{diff_fence}\n"
                        error_msg += "**Hint:** You need to match the target content exactly, including any whitespace and indentations."

                        action_errors.append(
                            ValidationError(
                                message=error_msg,
                                file_path=str(file_path),
                            )
                        )
                    elif matches > 1:
                        fence = get_fence_for_content(find_block)
                        action_errors.append(
                            ValidationError(
                                message=(
                                    f"The `FIND` block is ambiguous. Found {matches} matches in: {file_path}\n"
                                    f"**FIND Block:**\n"
                                    f"{fence}\n{find_block}\n{fence}"
                                ),
                                file_path=str(file_path),
                            )
                        )
        return action_errors
