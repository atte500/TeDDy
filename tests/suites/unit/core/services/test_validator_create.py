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


def test_validate_create_fails_if_file_exists(validator, mock_fs):
    """
    Given a CREATE action for a file that exists,
    When validated,
    Then it should return an error.
    """
    mock_fs.path_exists.return_value = True

    plan = Plan(
        title="Test",
        rationale="Test",
        actions=[
            ActionData(type="CREATE", params={"path": "existing.txt", "content": "foo"})
        ],
    )

    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "File already exists" in errors[0].message
    assert errors[0].file_path == "existing.txt"
