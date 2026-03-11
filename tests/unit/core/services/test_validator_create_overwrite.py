from unittest.mock import MagicMock
from teddy_executor.core.domain.models.plan import ActionData
from teddy_executor.core.services.validation_rules.create import CreateActionValidator
from teddy_executor.core.ports.outbound import IFileSystemManager


def test_create_validator_includes_overwrite_hint_when_file_exists():
    # Given a file system where the file exists
    fs_manager = MagicMock(spec=IFileSystemManager)
    fs_manager.path_exists.return_value = True
    validator = CreateActionValidator(fs_manager)

    # And a CREATE action targeting that file
    action = ActionData(
        type="CREATE", params={"path": "existing.txt"}, description="Try to create"
    )

    # When validating
    errors = validator.validate(action)

    # Then it should return a validation error with the hint
    assert len(errors) == 1
    assert "File already exists: existing.txt" in errors[0].message
    assert "Overwrite: true" in errors[0].message
    assert "parameter can be used with caution to bypass this" in errors[0].message


def test_create_validator_passes_when_file_exists_with_overwrite():
    # Given a file system where the file exists
    fs_manager = MagicMock(spec=IFileSystemManager)
    fs_manager.path_exists.return_value = True
    validator = CreateActionValidator(fs_manager)

    # And a CREATE action targeting that file WITH overwrite=True
    action = ActionData(
        type="CREATE",
        params={"path": "existing.txt", "overwrite": True},
        description="Force create",
    )

    # When validating
    errors = validator.validate(action)

    # Then it should return NO errors
    assert len(errors) == 0
