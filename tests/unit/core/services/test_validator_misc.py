from unittest.mock import MagicMock
import pytest

from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.services.plan_validator import PlanValidator
from teddy_executor.core.services.validation_rules.helpers import (
    IActionValidator,
    ValidationError,
)
from teddy_executor.core.services.validation_rules.create import CreateActionValidator
from teddy_executor.core.services.validation_rules.edit import EditActionValidator
from teddy_executor.core.services.validation_rules.execute import ExecuteActionValidator
from teddy_executor.core.services.validation_rules.read import ReadActionValidator


@pytest.fixture
def validator(container, mock_fs) -> IPlanValidator:
    """Resolves the PlanValidator from the container with all rules."""
    # Register individual rules; container will inject mock_fs automatically
    container.register(CreateActionValidator)
    container.register(EditActionValidator)
    container.register(ExecuteActionValidator)
    container.register(ReadActionValidator)

    # Register IPlanValidator implementation and its dependencies in one go
    container.register(
        IPlanValidator,
        PlanValidator,
        validators=[
            container.resolve(CreateActionValidator),
            container.resolve(EditActionValidator),
            container.resolve(ExecuteActionValidator),
            container.resolve(ReadActionValidator),
        ],
    )
    return container.resolve(IPlanValidator)


def test_plan_validator_uses_injected_validators(validator):
    # Arrange
    mock_validator = MagicMock(spec=IActionValidator)
    mock_validator.can_validate.return_value = True
    mock_validator.validate.return_value = [ValidationError(message="Mock Error")]

    plan = Plan(
        title="Test Plan",
        rationale="Test",
        actions=[ActionData(type="test_action", params={})],
    )

    # Injected via constructor in the fixture setup if we wanted, but we can also
    # just create a new one here to test the specific behavior.
    v = PlanValidator(file_system_manager=MagicMock(), validators=[mock_validator])

    # Act
    errors = v.validate(plan)

    # Assert
    assert len(errors) == 1
    assert errors[0].message == "Mock Error"
    mock_validator.can_validate.assert_called_once_with("test_action")
    mock_validator.validate.assert_called_once()


def test_validate_fails_for_unknown_action_type(validator):
    """
    Given a plan with an unknown action type,
    When validated,
    Then it should return an error.
    """
    plan = Plan(
        title="Test",
        rationale="Test",
        actions=[
            ActionData(type="EXECUTE", params={"command": "echo 'valid'"}),
            ActionData(type="UNKNOWN_ACTION", params={}),
        ],
    )

    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "Unknown action type: UNKNOWN_ACTION" in errors[0].message
