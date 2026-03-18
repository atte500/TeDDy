import pytest
from unittest.mock import MagicMock
from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.core.services.plan_validator import PlanValidator
from teddy_executor.core.ports.outbound import IFileSystemManager


@pytest.fixture
def mock_fs():
    return MagicMock(spec=IFileSystemManager)


def test_validate_rejects_edit_if_file_not_in_context(mock_fs):
    """
    PlanValidator.validate should return an error if an EDIT action
    targets a file not present in Session or Turn context.
    """
    # Given
    validator = PlanValidator(file_system_manager=mock_fs)
    plan = Plan(
        title="Test Plan",
        rationale="Testing context",
        actions=[
            ActionData(
                type="EDIT",
                params={
                    "path": "src/main.py",
                    "edits": [{"find": "a", "replace": "b"}],
                },
                description="Edit src/main.py",
            )
        ],
    )
    # File exists on disk but is not in context
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "a"

    context_paths = {"Session": ["README.md"], "Turn": ["docs/ARCH.md"]}

    # When
    # This is expected to fail because the signature doesn't support context_paths yet
    errors = validator.validate(plan, context_paths=context_paths)

    # Then
    assert len(errors) == 1
    assert "is not in the current turn context" in errors[0].message
    assert errors[0].file_path == "src/main.py"


def test_edit_validator_checks_context_before_existence(mock_fs):
    """
    To prevent leaking information about the filesystem, the EDIT validator
    must check if a file is in context BEFORE checking if it exists on disk.
    """
    # Given
    validator = PlanValidator(file_system_manager=mock_fs)
    plan = Plan(
        title="Test Plan",
        rationale="Testing context",
        actions=[
            ActionData(
                type="EDIT",
                params={"path": "secret/file.txt", "edits": []},
            )
        ],
    )
    # File does NOT exist on disk and is NOT in context
    mock_fs.path_exists.return_value = False
    context_paths = {"Session": [], "Turn": []}

    # When
    errors = validator.validate(plan, context_paths=context_paths)

    # Then: It should report 'not in context', not 'file does not exist'
    assert len(errors) == 1
    assert "is not in the current turn context" in errors[0].message


def test_validate_rejects_read_if_file_already_in_context(mock_fs):
    """
    PlanValidator.validate should return an error if a READ action
    targets a file already present in Session or Turn context.
    """
    # Given
    validator = PlanValidator(file_system_manager=mock_fs)
    plan = Plan(
        title="Test Plan",
        rationale="Testing context",
        actions=[
            ActionData(
                type="READ",
                params={"resource": "README.md"},
                description="Read README.md",
            )
        ],
    )
    mock_fs.path_exists.return_value = True

    context_paths = {"Session": ["README.md"], "Turn": []}

    # When
    errors = validator.validate(plan, context_paths=context_paths)

    # Then
    assert len(errors) == 1
    assert "is already in context" in errors[0].message
    assert errors[0].file_path == "README.md"


def test_validate_rejects_prune_if_file_not_in_turn_context(mock_fs):
    """
    PlanValidator.validate should return an error if a PRUNE action
    targets a file NOT present in the Turn context.
    """
    # Given
    validator = PlanValidator(file_system_manager=mock_fs)
    plan = Plan(
        title="Test Plan",
        rationale="Testing context",
        actions=[
            ActionData(
                type="PRUNE",
                params={"resource": "README.md"},
                description="Prune README.md",
            )
        ],
    )

    context_paths = {"Session": ["README.md"], "Turn": ["src/main.py"]}

    # When
    errors = validator.validate(plan, context_paths=context_paths)

    # Then
    assert len(errors) == 1
    assert "is not in the current turn context" in errors[0].message
    assert errors[0].file_path == "README.md"
