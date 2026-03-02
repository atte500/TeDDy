"""
Validation rules for the 'CREATE' action.
"""

from typing import List

from teddy_executor.core.domain.models.plan import ActionData
from teddy_executor.core.ports.outbound import IFileSystemManager
from teddy_executor.core.services.validation_rules.helpers import (
    PlanValidationError,
    ValidationError,
    validate_path_is_safe,
)


def validate_create_action(
    action: ActionData, file_system_manager: IFileSystemManager
) -> List[ValidationError]:
    """Validates a 'create' action."""
    try:
        path_str = action.params.get("path")
        if isinstance(path_str, str):
            validate_path_is_safe(path_str, "CREATE")
            if file_system_manager.path_exists(path_str):
                raise PlanValidationError(
                    f"File already exists: {path_str}", file_path=path_str
                )
        return []
    except PlanValidationError as e:
        return [ValidationError(message=e.message, file_path=e.file_path)]
