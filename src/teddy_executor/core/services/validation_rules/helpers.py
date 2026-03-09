"""
Shared helper classes and functions for validation rules.
"""

import os
from pathlib import Path
from typing import List, Optional, Protocol

from teddy_executor.core.domain.models.plan import ActionData, ValidationError


from typing import Dict, Sequence


class IActionValidator(Protocol):
    """
    Protocol for an action-specific validation rule.
    """

    def can_validate(self, action_type: str) -> bool:
        """Returns True if this validator can handle the given action type."""
        ...

    def validate(
        self,
        action: ActionData,
        context_paths: Optional[Dict[str, Sequence[str]]] = None,
    ) -> List[ValidationError]:
        """Validates the given action."""
        ...


class PlanValidationError(Exception):
    """Custom exception for plan validation errors."""

    def __init__(self, message: str, file_path: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.file_path = file_path


def validate_path_is_safe(path_str: str, action_type: str):
    """
    Ensures a file path is safe by checking for absolute paths and
    directory traversal attempts.
    """
    if os.path.isabs(path_str):
        raise PlanValidationError(
            f"Action `{action_type}` contains an absolute path, which is not allowed: {path_str}"
        )
    if ".." in Path(path_str).parts:
        raise PlanValidationError(
            f"Action `{action_type}` contains a directory traversal attempt ('..'), which is not allowed: {path_str}"
        )
