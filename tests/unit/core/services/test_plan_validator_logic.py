import pytest
from teddy_executor.core.domain.models import Plan, ActionData
from teddy_executor.core.services.plan_validator import PlanValidator


@pytest.fixture
def validator():
    return PlanValidator()


def test_validate_create_fails_if_file_exists(validator, fs):
    """
    Given a CREATE action for a file that exists,
    When validated,
    Then it should return an error.
    """
    fs.create_file("existing.txt", contents="old content")

    plan = Plan(
        title="Test",
        actions=[
            ActionData(type="CREATE", params={"path": "existing.txt", "content": "foo"})
        ],
    )

    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "File already exists" in errors[0].message
    assert errors[0].file_path == "existing.txt"


def test_validate_edit_fails_if_find_block_not_unique(validator, fs):
    """
    Given an EDIT action where the FIND block appears multiple times in the file,
    When validated,
    Then it should return an error.
    """
    content = "def foo():\n    pass\n\ndef foo():\n    pass"
    fs.create_file("source.py", contents=content)

    find_content = "def foo():\n    pass"
    plan = Plan(
        title="Test",
        actions=[
            ActionData(
                type="EDIT",
                params={
                    "path": "source.py",
                    "edits": [{"find": find_content, "replace": "bar"}],
                },
            )
        ],
    )

    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "Found 2 matches" in errors[0].message


def test_validate_edit_fails_if_find_and_replace_identical(validator, fs):
    """
    Given an EDIT action where FIND and REPLACE are identical,
    When validated,
    Then it should return an error.
    """
    fs.create_file("source.py", contents="same content")

    content = "same content"
    plan = Plan(
        title="Test",
        actions=[
            ActionData(
                type="EDIT",
                params={
                    "path": "source.py",
                    "edits": [{"find": content, "replace": content}],
                },
            )
        ],
    )

    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "FIND and REPLACE blocks are identical" in errors[0].message
