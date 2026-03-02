"""
Validation rules for the 'READ' action.
"""

from typing import List

from teddy_executor.core.domain.models.plan import ActionData
from teddy_executor.core.services.validation_rules.helpers import (
    PlanValidationError,
    ValidationError,
    validate_path_is_safe,
)


def validate_read_action(action: ActionData) -> List[ValidationError]:
    """Validates a 'read' action."""
    try:
        path_str = action.params.get("resource")
        # URLs are not file paths and should be ignored by this validator.
        if isinstance(path_str, str) and not path_str.startswith(
            ("http://", "https://")
        ):
            validate_path_is_safe(path_str, "READ")
        return []
    except PlanValidationError as e:
        return [ValidationError(message=e.message, file_path=e.file_path)]
