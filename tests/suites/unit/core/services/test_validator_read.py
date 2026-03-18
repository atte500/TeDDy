import pytest

from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.services.plan_validator import PlanValidator
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


def test_read_action_validator_reports_error_if_file_missing(validator, mock_fs):
    # Arrange
    mock_fs.path_exists.return_value = False

    plan = Plan(
        title="Test",
        rationale="Test",
        actions=[ActionData(type="READ", params={"resource": "nonexistent.txt"})],
    )

    # Act
    errors = validator.validate(plan)

    # Assert
    assert len(errors) == 1
    assert "File to read does not exist" in errors[0].message
    assert errors[0].file_path == "nonexistent.txt"
