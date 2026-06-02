"""
Consolidated validation rules for filesystem-related actions (CREATE, READ, PRUNE).
"""

from typing import Optional

from teddy_executor.core.domain.models.plan import ActionData, ValidationError
from teddy_executor.core.services.validation_rules.helpers import (
    BaseActionValidator,
    ContextPaths,
    ValidationResult,
)


class CreateActionValidator(BaseActionValidator):
    """Handles validation for the 'CREATE' action."""

    def validate(
        self,
        action: ActionData,
        context_paths: Optional[ContextPaths] = None,
    ) -> ValidationResult:
        """Performs pre-flight checks for CREATE."""
        target_path, validation_errs = self._get_validated_path(
            action, ["path"], "CREATE"
        )
        if validation_errs:
            return validation_errs

        if target_path and self._file_system_manager.path_exists(target_path):
            if not action.params.get("overwrite"):
                return [
                    ValidationError(
                        message=(
                            f"File already exists: {target_path}. **Hint:** The 'Overwrite: true' "
                            "parameter can be used with caution to bypass this."
                        ),
                        file_path=target_path,
                        offending_node=action.node,
                    )
                ]
        return []


class ReadActionValidator(BaseActionValidator):
    """Handles validation for the 'READ' action."""

    def validate(
        self,
        action: ActionData,
        context_paths: Optional[ContextPaths] = None,
    ) -> ValidationResult:
        """Performs pre-flight checks for READ."""
        src_resource, read_errors = self._get_validated_path(
            action, ["resource"], "READ"
        )
        if read_errors:
            return read_errors

        if (
            isinstance(src_resource, str)
            and not src_resource.startswith("http://")
            and not src_resource.startswith("https://")
        ):
            if not self._file_system_manager.path_exists(src_resource):
                return [
                    ValidationError(
                        message=f"File to read does not exist: {src_resource}",
                        file_path=src_resource,
                        offending_node=action.node,
                    )
                ]
        return read_errors
