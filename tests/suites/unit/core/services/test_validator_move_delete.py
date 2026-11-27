"""Validation rules for the MOVE and DELETE actions."""

import pytest

from teddy_executor.core.domain.models.plan import ActionData, Plan, ValidationError
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator


def _validate(container, action: ActionData) -> list[ValidationError]:
    """Run one action through the registered plan validator."""
    validator = container.resolve(IPlanValidator)
    return validator.validate(Plan(title="Test", rationale="Test", actions=[action]))


def test_move_rejects_missing_source(container, mock_fs):
    """
    Given a MOVE without a Source,
    When validated,
    Then the error names the missing parameter.
    """
    errors = _validate(
        container, ActionData(type="MOVE", params={"destination": "app/new.py"})
    )

    assert len(errors) == 1
    assert "Source" in errors[0].message


def test_move_rejects_missing_destination(container, mock_fs):
    """
    Given a MOVE without a Destination,
    When validated,
    Then the error names the missing parameter.
    """
    errors = _validate(
        container, ActionData(type="MOVE", params={"source": "app/old.py"})
    )

    assert len(errors) == 1
    assert "Destination" in errors[0].message


def test_move_rejects_missing_source_path(container, mock_fs):
    """
    Given a MOVE whose source does not exist,
    When validated,
    Then the error names the path.
    """
    mock_fs.path_exists.return_value = False

    errors = _validate(
        container,
        ActionData(
            type="MOVE", params={"source": "app/old.py", "destination": "app/new.py"}
        ),
    )

    assert len(errors) == 1
    assert "app/old.py" in errors[0].message
    assert errors[0].file_path == "app/old.py"


def test_move_rejects_occupied_destination(container, mock_fs):
    """
    Given a MOVE whose destination already exists,
    When validated,
    Then the error names the destination rather than the source.
    """
    mock_fs.path_exists.return_value = True

    errors = _validate(
        container,
        ActionData(
            type="MOVE", params={"source": "app/old.py", "destination": "app/new.py"}
        ),
    )

    assert len(errors) == 1
    assert "app/new.py" in errors[0].message
    assert errors[0].file_path == "app/new.py"


def test_move_rejects_rename_onto_itself(container, mock_fs):
    """
    Given a MOVE whose source and destination are identical,
    When validated,
    Then the error reports the no-op before any filesystem question.
    """
    mock_fs.path_exists.return_value = True

    errors = _validate(
        container,
        ActionData(
            type="MOVE", params={"source": "app/same.py", "destination": "app/same.py"}
        ),
    )

    assert len(errors) == 1
    assert "identical" in errors[0].message


@pytest.mark.parametrize(
    "params",
    [
        {"source": "../outside.py", "destination": "app/new.py"},
        {"source": "app/old.py", "destination": "/absolute/new.py"},
    ],
)
def test_move_rejects_unsafe_paths(container, mock_fs, params):
    """
    Given a MOVE whose source or destination escapes the project root,
    When validated,
    Then the shared path-safety rule rejects it.
    """
    errors = _validate(container, ActionData(type="MOVE", params=params))

    assert len(errors) == 1
    assert "not allowed" in errors[0].message


def test_move_accepts_valid_rename(container, mock_fs):
    """
    Given a MOVE whose source exists and destination does not,
    When validated,
    Then no error is reported.
    """
    mock_fs.path_exists.side_effect = lambda path: path == "app/old.py"

    errors = _validate(
        container,
        ActionData(
            type="MOVE", params={"source": "app/old.py", "destination": "app/new.py"}
        ),
    )

    assert errors == []


def test_delete_rejects_missing_path(container, mock_fs):
    """
    Given a DELETE without a Path,
    When validated,
    Then the error names the missing parameter.
    """
    errors = _validate(container, ActionData(type="DELETE", params={}))

    assert len(errors) == 1
    assert "Path" in errors[0].message


def test_delete_rejects_missing_target(container, mock_fs):
    """
    Given a DELETE whose target does not exist,
    When validated,
    Then the error names the path.
    """
    mock_fs.path_exists.return_value = False

    errors = _validate(
        container, ActionData(type="DELETE", params={"path": "app/legacy.py"})
    )

    assert len(errors) == 1
    assert "app/legacy.py" in errors[0].message


def test_delete_rejects_unsafe_path(container, mock_fs):
    """
    Given a DELETE on an absolute path,
    When validated,
    Then the shared path-safety rule rejects it.
    """
    errors = _validate(
        container, ActionData(type="DELETE", params={"path": "/etc/passwd"})
    )

    assert len(errors) == 1
    assert "not allowed" in errors[0].message


def test_delete_rejects_non_empty_directory_without_recursive(container, mock_fs):
    """
    Given a DELETE on a non-empty directory without Recursive,
    When validated,
    Then the error names the Recursive flag, because destruction must be explicit.
    """
    mock_fs.path_exists.return_value = True
    mock_fs.is_dir.return_value = True
    mock_fs.list_directory.return_value = ["legacy_child.py"]

    errors = _validate(
        container, ActionData(type="DELETE", params={"path": "app/legacy"})
    )

    assert len(errors) == 1
    assert "Recursive" in errors[0].message


def test_delete_accepts_empty_directory_without_recursive(container, mock_fs):
    """
    Given a DELETE on an empty directory without Recursive,
    When validated,
    Then no error is reported, because nothing is destroyed implicitly.
    """
    mock_fs.path_exists.return_value = True
    mock_fs.is_dir.return_value = True
    mock_fs.list_directory.return_value = []

    errors = _validate(
        container, ActionData(type="DELETE", params={"path": "app/legacy"})
    )

    assert errors == []


def test_delete_accepts_non_empty_directory_with_recursive(container, mock_fs):
    """
    Given a DELETE on a non-empty directory with Recursive true,
    When validated,
    Then no error is reported.
    """
    mock_fs.path_exists.return_value = True
    mock_fs.is_dir.return_value = True
    mock_fs.list_directory.return_value = ["legacy_child.py"]

    errors = _validate(
        container,
        ActionData(type="DELETE", params={"path": "app/legacy", "recursive": True}),
    )

    assert errors == []


def test_delete_accepts_file_without_recursive(container, mock_fs):
    """
    Given a DELETE on a file without Recursive,
    When validated,
    Then no error is reported, because a file needs no flag.
    """
    mock_fs.path_exists.return_value = True
    mock_fs.is_dir.return_value = False

    errors = _validate(
        container, ActionData(type="DELETE", params={"path": "app/legacy.py"})
    )

    assert errors == []
