from typing import Optional

from teddy_executor.core.domain.models.plan import ActionData, ValidationError
from teddy_executor.core.services.validation_rules.helpers import (
    BaseActionValidator,
    ContextPaths,
    ValidationResult,
)


class MessageActionValidator(BaseActionValidator):
    """
    Validates MESSAGE actions.
    """

    def validate(
        self,
        action: ActionData,
        context_paths: Optional[ContextPaths] = None,
    ) -> ValidationResult:
        content = action.params.get("content")
        if not content or not isinstance(content, str) or not content.strip():
            return [
                ValidationError(
                    message="MESSAGE action must have non-empty content.",
                    offending_node=action.node,
                )
            ]
        return []
