"""
Validation rules for the 'EXECUTE' action.
"""

from typing import Optional

from teddy_executor.core.domain.models.plan import ActionData, ValidationError
from teddy_executor.core.services.validation_rules.helpers import (
    BaseActionValidator,
    ContextPaths,
    ValidationResult,
)


class ExecuteActionValidator(BaseActionValidator):
    """Checks for command content and valid working directory."""

    def validate(
        self,
        action: ActionData,
        context_paths: Optional[ContextPaths] = None,
    ) -> ValidationResult:
        cmd_text = action.params.get("command", "").strip()
        errors: ValidationResult = []

        _, path_errs = self._get_validated_path(action, ["cwd"], "EXECUTE")
        errors.extend(path_errs)

        if not cmd_text:
            errors.append(
                ValidationError(message="EXECUTE action must contain a command")
            )

        return errors


# Removed legacy functional validation rule in favor of ExecuteActionValidator class.
