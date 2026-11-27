"""
Consolidated validation rules for filesystem-related actions
(CREATE, READ, MOVE, DELETE).
"""

from typing import Optional

from teddy_executor.core.domain.models.plan import ActionData, ValidationError
from teddy_executor.core.services.validation_rules.helpers import (
    BaseActionValidator,
    ContextPaths,
    PlanValidationError,
    ValidationResult,
    validate_path_is_safe,
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


class MoveActionValidator(BaseActionValidator):
    """Handles validation for the 'MOVE' action."""

    def validate(
        self,
        action: ActionData,
        context_paths: Optional[ContextPaths] = None,
    ) -> ValidationResult:
        """Performs pre-flight checks for MOVE."""
        source = action.params.get("source")
        destination = action.params.get("destination")

        missing = [
            name
            for name, value in (("Source", source), ("Destination", destination))
            if not isinstance(value, str) or not value
        ]
        if missing:
            return [
                ValidationError(
                    message=f"MOVE action requires a '{missing[0]}' parameter.",
                    offending_node=action.node,
                )
            ]

        if source == destination:
            return [
                ValidationError(
                    message=(
                        f"MOVE source and destination are identical: {source}. "
                        "A rename onto itself rewrites nothing."
                    ),
                    file_path=source,
                    offending_node=action.node,
                )
            ]

        for path_str in (source, destination):
            try:
                validate_path_is_safe(path_str, "MOVE")
            except PlanValidationError as e:
                return [
                    ValidationError(
                        message=e.message,
                        file_path=e.file_path or path_str,
                        offending_node=action.node,
                    )
                ]

        if not self._file_system_manager.path_exists(source):
            return [
                ValidationError(
                    message=f"Source path does not exist: {source}",
                    file_path=source,
                    offending_node=action.node,
                )
            ]

        if self._file_system_manager.path_exists(destination):
            return [
                ValidationError(
                    message=(
                        f"Destination path already exists: {destination}. "
                        "MOVE carries no overwrite escape hatch, because "
                        "replacing a destination silently discards work."
                    ),
                    file_path=destination,
                    offending_node=action.node,
                )
            ]

        return []


class DeleteActionValidator(BaseActionValidator):
    """Handles validation for the 'DELETE' action."""

    def validate(
        self,
        action: ActionData,
        context_paths: Optional[ContextPaths] = None,
    ) -> ValidationResult:
        """Performs pre-flight checks for DELETE."""
        path_str = action.params.get("path")

        if not isinstance(path_str, str) or not path_str:
            return [
                ValidationError(
                    message="DELETE action requires a 'Path' parameter.",
                    offending_node=action.node,
                )
            ]

        try:
            validate_path_is_safe(path_str, "DELETE")
        except PlanValidationError as e:
            return [
                ValidationError(
                    message=e.message,
                    file_path=e.file_path or path_str,
                    offending_node=action.node,
                )
            ]

        file_system_manager = self._file_system_manager
        if not file_system_manager.path_exists(path_str):
            return [
                ValidationError(
                    message=f"Path to delete does not exist: {path_str}",
                    file_path=path_str,
                    offending_node=action.node,
                )
            ]

        recursive = action.params.get("recursive", False)
        if (
            not recursive
            and file_system_manager.is_dir(path_str)
            and file_system_manager.list_directory(path_str)
        ):
            return [
                ValidationError(
                    message=(
                        f"Directory is not empty: {path_str}. **Hint:** The "
                        "'Recursive: true' parameter can be used to remove it "
                        "together with everything beneath it."
                    ),
                    file_path=path_str,
                    offending_node=action.node,
                )
            ]

        return []
