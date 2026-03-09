"""
Validation rules for the 'EXECUTE' action.
"""

from pathlib import Path
from typing import Dict, List, Optional, Sequence

from teddy_executor.core.domain.models.plan import ActionData
from teddy_executor.core.services.validation_rules.helpers import (
    IActionValidator,
    ValidationError,
)


class ExecuteActionValidator(IActionValidator):
    """Validator for the 'EXECUTE' action."""

    def can_validate(self, action_type: str) -> bool:
        return action_type.lower() == "execute"

    def validate(
        self,
        action: ActionData,
        context_paths: Optional[Dict[str, Sequence[str]]] = None,
    ) -> List[ValidationError]:
        """Validates an 'execute' action."""
        errors: List[ValidationError] = []
        command = action.params.get("command", "").strip()
        cwd = action.params.get("cwd")

        if cwd:
            if error := _check_cwd_safety(cwd):
                errors.append(error)

        if not command:
            errors.append(
                ValidationError(message="EXECUTE action must contain a command")
            )
            return errors

        return errors


def _check_cwd_safety(cwd: str) -> Optional[ValidationError]:
    """Checks if the cwd is safe (not absolute, no traversal)."""
    # Explicitly check for POSIX-style absolute paths for cross-platform safety
    if cwd.startswith("/"):
        return ValidationError(
            message=f"CWD '{cwd}' is an absolute path and is not allowed"
        )

    p = Path(cwd)
    if p.is_absolute():
        return ValidationError(
            message=f"CWD '{cwd}' is an absolute path and is not allowed"
        )
    # Check for path traversal attempts using pathlib
    if ".." in p.parts:
        return ValidationError(message=f"CWD '{cwd}' is outside the project directory")
    return None


# Removed legacy functional validation rule in favor of ExecuteActionValidator class.
