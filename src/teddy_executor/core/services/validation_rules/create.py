"""
Validation rules for the 'CREATE' action.
"""

from typing import Dict, List, Optional, Sequence

from teddy_executor.core.domain.models.plan import ActionData
from teddy_executor.core.services.validation_rules.helpers import (
    BaseActionValidator,
    PlanValidationError,
    ValidationError,
    validate_path_is_safe,
)


class CreateActionValidator(BaseActionValidator):
    """Validator for the 'CREATE' action."""

    def validate(
        self,
        action: ActionData,
        context_paths: Optional[Dict[str, Sequence[str]]] = None,
    ) -> List[ValidationError]:
        """Validates a 'create' action."""
        try:
            path_str = action.params.get("path")
            if isinstance(path_str, str):
                validate_path_is_safe(path_str, "CREATE")
                if self._file_system_manager.path_exists(path_str):
                    if not action.params.get("overwrite"):
                        msg = (
                            f"File already exists: {path_str}. Hint: The 'Overwrite: true' "
                            "parameter can be used with caution to bypass this."
                        )
                        raise PlanValidationError(msg, file_path=path_str)
            return []
        except PlanValidationError as e:
            return [
                ValidationError(
                    message=e.message,
                    file_path=e.file_path,
                    offending_node=action.node,
                )
            ]


# Removed legacy functional validation rule in favor of CreateActionValidator class.
