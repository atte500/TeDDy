"""
Consolidated validation rules for filesystem-related actions (CREATE, READ, PRUNE).
"""

from typing import Optional

from teddy_executor.core.domain.models.plan import ActionData, ValidationError
from teddy_executor.core.services.validation_rules.helpers import (
    BaseActionValidator,
    ContextPaths,
    ValidationResult,
    is_path_in_context,
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

        if src_resource and is_path_in_context(src_resource, context_paths):
            return [
                ValidationError(
                    message=f"{src_resource} is already in context",
                    file_path=src_resource,
                    offending_node=action.node,
                )
            ]

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


class PruneActionValidator(BaseActionValidator):
    """Handles validation for the 'PRUNE' action."""

    def validate(
        self,
        action: ActionData,
        context_paths: Optional[ContextPaths] = None,
    ) -> ValidationResult:
        """Performs pre-flight checks for PRUNE."""
        resource, errors = self._get_validated_path(action, ["resource"], "PRUNE")
        if not resource:
            return [
                ValidationError(message="PRUNE action missing 'resource' parameter.")
            ]
        if errors:
            return errors

        if context_paths is not None:
            if not is_path_in_context(
                resource, context_paths, check_session=False, check_turn=True
            ):
                return [
                    ValidationError(
                        message=f"{resource} is not in the current turn context",
                        file_path=resource,
                        offending_node=action.node,
                    )
                ]

        return []
