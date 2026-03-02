"""
This module contains the implementation of the PlanValidator service.
"""

from typing import List, Optional

from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.services.validation_rules.create import validate_create_action
from teddy_executor.core.services.validation_rules.edit import validate_edit_action
from teddy_executor.core.services.validation_rules.execute import (
    validate_execute_action,
)
from teddy_executor.core.services.validation_rules.helpers import ValidationError
from teddy_executor.core.services.validation_rules.read import validate_read_action


class PlanValidator(IPlanValidator):
    """
    Implements IPlanValidator using a strategy pattern to run pre-flight checks.
    """

    def validate(self, plan: Plan) -> List[ValidationError]:
        """
        Validates a plan by dispatching each action to a specific validation method.

        Returns:
            A list of validation error objects. An empty list signifies success.
        """
        errors: List[ValidationError] = []
        for action in plan.actions:
            # Manual dispatching based on action type
            action_type_lower = action.type.lower()
            action_errors: Optional[List[ValidationError]] = None

            if action_type_lower == "create":
                action_errors = validate_create_action(action)
            elif action_type_lower == "edit":
                action_errors = validate_edit_action(action)
            elif action_type_lower == "execute":
                action_errors = validate_execute_action(action)
            elif action_type_lower == "read":
                action_errors = validate_read_action(action)

            if action_errors:
                errors.extend(action_errors)
        return errors
