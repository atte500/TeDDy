"""
Validation rules for the 'READ' action.
"""

from typing import Dict, List, Optional, Sequence

from teddy_executor.core.domain.models.plan import ActionData
from teddy_executor.core.services.validation_rules.helpers import (
    BaseActionValidator,
    PlanValidationError,
    ValidationError,
    is_path_in_context,
    validate_path_is_safe,
)


class ReadActionValidator(BaseActionValidator):
    """Validator for the 'READ' action."""

    def validate(
        self,
        action: ActionData,
        context_paths: Optional[Dict[str, Sequence[str]]] = None,
    ) -> List[ValidationError]:
        """Validates a 'read' action."""
        errors: List[ValidationError] = []
        try:
            path_str = action.params.get("resource")
            used_alias = action.params.get("metadata_used_file_path_alias", False)

            if (
                used_alias
                and isinstance(path_str, str)
                and (path_str.startswith("http://") or path_str.startswith("https://"))
            ):
                errors.append(
                    ValidationError(
                        message="Strict Local Only: 'File Path' alias does not support URLs",
                        file_path=path_str,
                        offending_node=action.node,
                    )
                )
                return errors

            # Context Check: READ must NOT be in context
            if path_str and is_path_in_context(path_str, context_paths):
                errors.append(
                    ValidationError(
                        message=f"{path_str} is already in context",
                        file_path=path_str,
                        offending_node=action.node,
                    )
                )

            if (
                isinstance(path_str, str)
                and not path_str.startswith("http://")
                and not path_str.startswith("https://")
            ):
                validate_path_is_safe(path_str, "READ")
                if not self._file_system_manager.path_exists(path_str):
                    raise PlanValidationError(
                        f"File to read does not exist: {path_str}", file_path=path_str
                    )
            return errors
        except PlanValidationError as e:
            errors.append(
                ValidationError(
                    message=e.message,
                    file_path=e.file_path,
                    offending_node=action.node,
                )
            )
            return errors


# Removed legacy functional validation rule in favor of ReadActionValidator class.
