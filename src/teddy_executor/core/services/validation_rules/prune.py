"""
Validation rules for the 'PRUNE' action.
"""

from typing import Dict, List, Optional, Sequence

from teddy_executor.core.domain.models.plan import ActionData
from teddy_executor.core.ports.outbound import IFileSystemManager
from teddy_executor.core.services.validation_rules.helpers import (
    IActionValidator,
    ValidationError,
)


class PruneActionValidator(IActionValidator):
    """Validator for the 'PRUNE' action."""

    def __init__(self, file_system_manager: IFileSystemManager):
        self._file_system_manager = file_system_manager

    def can_validate(self, action_type: str) -> bool:
        return action_type.lower() == "prune"

    def validate(
        self,
        action: ActionData,
        context_paths: Optional[Dict[str, Sequence[str]]] = None,
    ) -> List[ValidationError]:
        """Validates a 'prune' action."""
        resource = action.params.get("resource")
        if not resource:
            return [
                ValidationError(
                    message="PRUNE action missing 'resource' parameter.",
                )
            ]

        errors = []
        if context_paths:
            turn_context = context_paths.get("Turn", [])
            if resource not in turn_context:
                errors.append(
                    ValidationError(
                        message=f"{resource} is not in the current turn context",
                        file_path=resource,
                    )
                )

        return errors
