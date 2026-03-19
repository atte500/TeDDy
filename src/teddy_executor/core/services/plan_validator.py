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
        if validators is not None:
            self._validators = validators
        else:
            # Default set of validators for backward compatibility and ease of use
            from teddy_executor.core.services.validation_rules.create import (
                CreateActionValidator,
            )
            from teddy_executor.core.services.validation_rules.edit import (
                EditActionValidator,
            )
            from teddy_executor.core.services.validation_rules.execute import (
                ExecuteActionValidator,
            )
            from teddy_executor.core.services.validation_rules.read import (
                ReadActionValidator,
            )
            from teddy_executor.core.services.validation_rules.prune import (
                PruneActionValidator,
            )

            # Fallback for isolation (e.g. unit tests without a full container)
            # We use a neutral config service that just returns defaults.
            from teddy_executor.adapters.outbound.yaml_config_adapter import (
                YamlConfigAdapter,
            )

            config_service = YamlConfigAdapter(config_path="/nonexistent")
            self._validators = [
                CreateActionValidator(file_system_manager),
                EditActionValidator(file_system_manager, config_service),
                ExecuteActionValidator(),
                ReadActionValidator(file_system_manager),
                PruneActionValidator(file_system_manager),
            ]

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
