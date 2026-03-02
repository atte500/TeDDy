"""
Shared helper classes and functions for validation rules.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ValidationError:
    """Represents a structured validation error."""

    message: str
    file_path: Optional[str] = None


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
