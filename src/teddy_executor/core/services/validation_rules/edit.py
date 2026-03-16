"""
Validation rules for the 'EDIT' action.
"""

import os
from typing import Dict, List, Optional, Sequence

from teddy_executor.core.domain.models.plan import ActionData
from teddy_executor.core.services.validation_rules.edit_matcher import (
    find_best_match_and_diff,
)
from teddy_executor.core.services.validation_rules.helpers import (
    BaseActionValidator,
    PlanValidationError,
    ValidationError,
    is_path_in_context,
    validate_path_is_safe,
)
from teddy_executor.core.utils.markdown import get_fence_for_content


class EditActionValidator(BaseActionValidator):
    """Validator for the 'EDIT' action."""

    def validate(
        self,
        action: ActionData,
        context_paths: Optional[Dict[str, Sequence[str]]] = None,
    ) -> List[ValidationError]:
        """
        Validates an 'edit' action.
        """
        path_str = (
            action.params.get("path")
            or action.params.get("file_path")
            or action.params.get("File Path")
        )

        if not isinstance(path_str, str):
            return []

        try:
            validate_path_is_safe(path_str, "EDIT")

            # Context Check: EDIT must be in context
            if context_paths is not None:
                if not is_path_in_context(path_str, context_paths):
                    raise PlanValidationError(
                        f"{path_str} is not in the current turn context",
                        file_path=path_str,
                    )

            if not self._file_system_manager.path_exists(path_str):
                raise PlanValidationError(
                    f"File to edit does not exist: {path_str}",
                    file_path=path_str,
                )

        except (PlanValidationError, FileNotFoundError) as e:
            return [
                ValidationError(
                    message=getattr(e, "message", str(e)),
                    file_path=getattr(e, "file_path", path_str),
                    offending_node=action.node,
                )
            ]

        action_errors: List[ValidationError] = []
        content = self._file_system_manager.read_file(path_str)

        threshold = action.params.get("similarity_threshold")
        edits = action.params.get("edits")
        if isinstance(edits, list):
            for edit in edits:
                for err in _validate_single_edit(edit, content, path_str, threshold):
                    # Attach specific FIND CodeBlock node for surgical diagnostics
                    # Fallback to action node if find_node is missing
                    offending_node = edit.get("find_node") or action.node
                    action_errors.append(
                        ValidationError(
                            message=err.message,
                            file_path=err.file_path,
                            offending_node=offending_node,
                        )
                    )
        return action_errors


def _validate_single_edit(
    edit: dict, content: str, file_path: str, threshold: Optional[float] = None
) -> List[ValidationError]:
    """Validates a single edit dictionary."""
    errors: List[ValidationError] = []
    find_block = edit.get("find")
    replace_block = edit.get("replace")

    if os.environ.get("TEDDY_DEBUG"):
        print("\n--- TEDDY DEBUG: PlanValidator ---")
        print(f"File: {file_path}")
        print(f"Content (repr): {repr(content)}")
        print(f"Find Block (repr): {repr(find_block)}")
        print("--- END TEDDY DEBUG ---\n")

    if isinstance(find_block, str):
        if find_block == replace_block:
            fence = get_fence_for_content(find_block)
            errors.append(
                ValidationError(
                    message=(
                        f"FIND and REPLACE blocks are identical in: "
                        f"{file_path}\n"
                        f"**Block Content:**\n"
                        f"{fence}\n{find_block}\n{fence}"
                    ),
                    file_path=str(file_path),
                )
            )
            return errors

        # Use the resilient matcher for all matching logic
        matcher_kwargs = {}
        if threshold is not None:
            matcher_kwargs["threshold"] = threshold

        diff_text, score, is_ambiguous = find_best_match_and_diff(
            content, find_block, **matcher_kwargs
        )

        effective_threshold = threshold if threshold is not None else 0.95
        fence = get_fence_for_content(find_block)

        if is_ambiguous:
            errors.append(
                ValidationError(
                    message=(
                        f"The `FIND` block is ambiguous in: {file_path}\n"
                        f"**Similarity Score:** {score:.2f}\n"
                        f"**FIND Block:**\n"
                        f"{fence}\n{find_block}\n{fence}\n"
                        "**Hint:** Please provide a larger FIND block to uniquely identify the section and consider refactoring the target code to avoid duplication."
                    ),
                    file_path=str(file_path),
                )
            )
        elif score < effective_threshold:
            error_msg = (
                f"The `FIND` block could not be located in the file: "
                f"{file_path}\n"
                f"**Similarity Score:** {score:.2f}\n"
                f"**Similarity Threshold:** {effective_threshold:.2f}\n"
                f"**FIND Block:**\n"
                f"{fence}\n{find_block}\n{fence}\n"
            )
            if diff_text:
                diff_fence = get_fence_for_content(diff_text)
                error_msg += (
                    f"**Closest Match Diff:**\n{diff_fence}diff\n"
                    f"{diff_text}\n{diff_fence}\n"
                )
            error_msg += (
                "**Hint:** Review the provided diff and make sure to match the target content "
                "exactly, including whitespace and indentations."
            )
            errors.append(ValidationError(message=error_msg, file_path=str(file_path)))
    return errors


# Removed legacy functional validation rule in favor of EditActionValidator class.
