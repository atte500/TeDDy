from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator


def test_validate_create_fails_if_file_exists(container, mock_fs):
    """
    Given a CREATE action for a file that exists,
    When validated,
    Then it should return an error.
    """
    validator = container.resolve(IPlanValidator)
    mock_fs.path_exists.return_value = True
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
