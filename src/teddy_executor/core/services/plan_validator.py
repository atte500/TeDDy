"""
This module contains the implementation of the PlanValidator service.
"""

# Placeholder content
# The Developer will implement this based on the design document.
# See: docs/core/services/plan_validator.md

import os
from pathlib import Path
from typing import List

from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator


class PlanValidationError(Exception):
    """Custom exception for plan validation errors."""

    pass


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

    def validate(self, plan: Plan) -> List[str]:
        """
        Validates a plan by dispatching each action to a specific validation method.

        Returns:
            A list of validation error strings. An empty list signifies success.
        """
        errors: List[str] = []
        for action in plan.actions:
            # Normalize action type to lowercase to match method names
            validator_method = getattr(
                self, f"_validate_{action.type.lower()}_action", None
            )
            if validator_method:
                try:
                    validator_method(action)
                except PlanValidationError as e:
                    errors.append(str(e))
        return errors

    def _validate_create_action(self, action: ActionData):
        """Validates a 'create' action."""
        path_str = action.params.get("path")
        if isinstance(path_str, str):
            self._validate_path_is_safe(path_str, "CREATE")

    def _validate_read_action(self, action: ActionData):
        """Validates a 'read' action."""
        path_str = action.params.get("resource")
        # URLs are not file paths and should be ignored by this validator.
        if isinstance(path_str, str) and not path_str.startswith(
            ("http://", "https://")
        ):
            self._validate_path_is_safe(path_str, "READ")

    def _validate_edit_action(self, action: ActionData):
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
            return

        self._validate_path_is_safe(path_str, "EDIT")

        file_path = Path(path_str)
        if not file_path.exists():
            raise PlanValidationError(f"File to edit does not exist: {file_path}")

        content = file_path.read_text()

        # Handle 'edits' list (from Markdown parser)
        edits = action.params.get("edits")
        if isinstance(edits, list):
            for edit in edits:
                find_block = edit.get("find")
                if os.environ.get("TEDDY_DEBUG"):
                    print("\n--- TEDDY DEBUG: PlanValidator ---")
                    print(f"File: {file_path}")
                    print(f"Content (repr): {repr(content)}")
                    print(f"Find Block (repr): {repr(find_block)}")
                    print("--- END TEDDY DEBUG ---\n")
                if isinstance(find_block, str) and find_block not in content:
                    raise PlanValidationError(
                        f"The `FIND` block could not be located in the file: {file_path}"
                    )
        else:
            # Handle single 'find' param (legacy/YAML parser)
            find_block = action.params.get("find") or action.params.get("FIND")
            if isinstance(find_block, str) and find_block not in content:
                raise PlanValidationError(
                    f"The `FIND` block could not be located in the file: {file_path}"
                )
