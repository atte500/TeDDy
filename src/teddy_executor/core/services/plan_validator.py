"""
This module contains the implementation of the PlanValidator service.
"""

from typing import Dict, List, Optional, Sequence

from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.services.validation_rules.helpers import (
    IActionValidator,
    ValidationError,
)


from teddy_executor.core.ports.outbound import IFileSystemManager


class PlanValidator(IPlanValidator):
    """
    Implements IPlanValidator using a strategy pattern to run pre-flight checks.
    """

    def __init__(
        self,
        file_system_manager: IFileSystemManager,
        validators: Optional[List[IActionValidator]] = None,
    ):
        self._file_system_manager = file_system_manager
        self._validators = validators or []

    def validate(
        self, plan: Plan, context_paths: Optional[Dict[str, Sequence[str]]] = None
    ) -> List[ValidationError]:
        """
        Validates a plan by dispatching each action to a specific validation method.

        Returns:
            A list of validation error objects. An empty list signifies success.
        """
        errors: List[ValidationError] = []
        for action in plan.actions:
            action_type_lower = action.type.lower()
            action_errors: Optional[List[ValidationError]] = None

            # New registry-based dispatching
            handled_by_injected = False
            for validator in self._validators:
                if validator.can_validate(action_type_lower):
                    action_errors = validator.validate(
                        action, context_paths=context_paths
                    )
                    handled_by_injected = True
                    break

            if handled_by_injected:
                if action_errors:
                    errors.extend(action_errors)
            elif action_type_lower in [
                "research",
                "prompt",
                "invoke",
                "return",
            ]:
                # These actions have no validation rules currently
                pass
            else:
                errors.append(
                    ValidationError(
                        message=f"Unknown action type: {action.type}",
                        file_path=action.params.get("path"),
                    )
                )
        return errors
