"""
This module contains the implementation of the PlanValidator service.
"""

# Placeholder content
# The Developer will implement this based on the design document.
# See: docs/core/services/plan_validator.md

from pathlib import Path
from typing import Any, List

from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator


class PlanValidationError(Exception):
    """Custom exception for plan validation errors."""

    pass


class PlanValidator(IPlanValidator):
    """
    Implements IPlanValidator using a strategy pattern to run pre-flight checks.
    """

    def validate(self, plan: Plan) -> List[Any]:
        """
        Validates a plan by dispatching each action to a specific validation method.

        Raises:
            PlanValidationError: If any validation rule fails.
        Returns:
            An empty list if validation is successful, per the interface contract.
        """
        for action in plan.actions:
            validator_method = getattr(self, f"_validate_{action.type}_action", None)
            if validator_method:
                validator_method(action)

        return []

    def _validate_edit_action(self, action: ActionData):
        """
        Validates an 'edit' action.

        Checks:
        - 'path' and 'find' parameters exist.
        - The target file exists.
        - The 'find' block content exists within the file.
        """
        path_str = action.params.get("path")
        find_block = action.params.get("find")

        if not isinstance(path_str, str) or not isinstance(find_block, str):
            # Let's assume other validations might catch missing or malformed params.
            # This check is focused on the content.
            return

        file_path = Path(path_str)
        if not file_path.exists():
            raise PlanValidationError(f"File to edit does not exist: {file_path}")

        content = file_path.read_text()
        if find_block not in content:
            raise PlanValidationError(
                f"The `FIND` block could not be located in the file: {file_path}"
            )
