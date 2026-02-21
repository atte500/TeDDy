"""
This module contains the implementation of the PlanValidator service.
"""

# Placeholder content
# The Developer will implement this based on the design document.
# See: docs/architecture/core/services/plan_validator.md

import os
from pathlib import Path
from typing import List

from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator


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
                        action_errors.append(
                            ValidationError(
                                message=(
                                    f"FIND and REPLACE blocks are identical in: {file_path}\n"
                                    f"**Block Content:**\n"
                                    f"```\n{find_block}\n```"
                                ),
                                file_path=str(file_path),
                            )
                        )
                        continue

                    matches = content.count(find_block)
                    if matches == 0:
                        action_errors.append(
                            ValidationError(
                                message=(
                                    f"The `FIND` block could not be located in the file: {file_path}\n"
                                    f"**FIND Block:**\n"
                                    f"```\n{find_block}\n```\n"
                                    f"**Hint:** Try to provide more context in the FIND block and match the content exactly, including whitespace and indentations."
                                ),
                                file_path=str(file_path),
                            )
                        )
                    elif matches > 1:
                        action_errors.append(
                            ValidationError(
                                message=(
                                    f"The `FIND` block is ambiguous. Found {matches} matches in: {file_path}\n"
                                    f"**FIND Block:**\n"
                                    f"```\n{find_block}\n```"
                                ),
                                file_path=str(file_path),
                            )
                        )
        else:
            # Handle single 'find' param (legacy/YAML parser)
            find_block = action.params.get("find") or action.params.get("FIND")
            replace_block = action.params.get("replace") or action.params.get("REPLACE")

            if isinstance(find_block, str):
                if find_block == replace_block:
                    action_errors.append(
                        ValidationError(
                            message=(
                                f"FIND and REPLACE blocks are identical in: {file_path}\n"
                                f"**Block Content:**\n"
                                f"```\n{find_block}\n```"
                            ),
                            file_path=str(file_path),
                        )
                    )
                elif find_block not in content:
                    action_errors.append(
                        ValidationError(
                            message=(
                                f"The `FIND` block could not be located in the file: {file_path}\n"
                                f"**FIND Block:**\n"
                                f"```\n{find_block}\n```\n"
                                f"**Hint:** Try to provide more context in the FIND block and match the content exactly, including whitespace and indentations."
                            ),
                            file_path=str(file_path),
                        )
                    )

        return action_errors
