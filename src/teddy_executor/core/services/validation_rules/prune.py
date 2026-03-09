"""
Validation rules for the 'PRUNE' action.
"""

from typing import Dict, List, Optional, Sequence

from teddy_executor.core.domain.models.plan import ActionData
from teddy_executor.core.services.validation_rules.helpers import (
    BaseActionValidator,
    ValidationError,
    is_path_in_context,
)


class PruneActionValidator(BaseActionValidator):
    """Validator for the 'PRUNE' action."""

    def validate(
        self,
        action: ActionData,
        context_paths: Optional[Dict[str, Sequence[str]]] = None,
    ) -> List[ValidationError]:
        """Validates a 'prune' action."""
        resource = action.params.get("resource")
        if not resource:
            return [
                ValidationError(
                    message="PRUNE action missing 'resource' parameter.",
                )
            ]

        errors = []
        # PRUNE must be in TURN context ONLY
        if context_paths is not None:
            if not is_path_in_context(
                resource, context_paths, check_session=False, check_turn=True
            ):
                errors.append(
                    ValidationError(
                        message=f"{resource} is not in the current turn context",
                        file_path=resource,
                    )
                )

        return errors
