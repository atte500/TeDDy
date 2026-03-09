"""
Shared helper classes and functions for validation rules.
"""

import os
from pathlib import Path
from abc import ABC
from typing import Dict, List, Optional, Protocol, Sequence

from teddy_executor.core.domain.models.plan import ActionData, ValidationError
from teddy_executor.core.ports.outbound import IFileSystemManager


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


class BaseActionValidator(ABC, IActionValidator):
    """Base class for action validators to reduce boilerplate."""

    def __init__(self, file_system_manager: IFileSystemManager):
        self._file_system_manager = file_system_manager

    def can_validate(self, action_type: str) -> bool:
        # This assumes the class name follows the pattern [ActionType]ActionValidator
        expected_prefix = self.__class__.__name__.replace("ActionValidator", "").lower()
        return action_type.lower() == expected_prefix


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


def is_path_in_context(
    path_str: str,
    context_paths: Optional[Dict[str, Sequence[str]]],
    check_session: bool = True,
    check_turn: bool = True,
) -> bool:
    """
    Checks if a path (normalized) is present in the specified context scopes.
    """
    if not context_paths or not path_str:
        return False

    scopes = []
    if check_session:
        scopes.append("Session")
    if check_turn:
        scopes.append("Turn")

    normalized_target = path_str.lstrip("/")

    for scope in scopes:
        context_files = context_paths.get(scope, [])
        normalized_context = [p.lstrip("/") for p in context_files]
        if normalized_target in normalized_context:
            return True

    return False
