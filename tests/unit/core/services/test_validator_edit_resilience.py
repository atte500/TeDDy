from unittest.mock import MagicMock
import pytest
from teddy_executor.core.domain.models.plan import ActionData
from teddy_executor.core.services.validation_rules.edit import EditActionValidator


@pytest.fixture
def mock_fs():
    return MagicMock()


def test_validator_handles_ambiguity(mock_fs):
    content = "block1\nblock2\n"
    mock_fs.read_file.return_value = content
    mock_fs.path_exists.return_value = True

    validator = EditActionValidator(mock_fs, MagicMock())
    action = ActionData(
        type="EDIT",
        description="test",
        params={
            "path": "test.py",
            "edits": [{"find": "block", "replace": "new", "find_node": None}],
        },
    )

    # Use 'Turn' scope as expected by helpers.is_path_in_context
    errors = validator.validate(action, context_paths={"Turn": ["test.py"]})
    assert len(errors) == 1
    assert "ambiguous" in errors[0].message.lower()
    assert "Similarity Score" in errors[0].message


def test_validator_respects_custom_threshold(mock_fs):
    content = "def hello():\n    pass\n"
    mock_fs.read_file.return_value = content
    mock_fs.path_exists.return_value = True

    validator = EditActionValidator(mock_fs, MagicMock())

    # Threshold 0.99 with a minor mismatch (extra space)
    action = ActionData(
        type="EDIT",
        description="test",
        params={
            "path": "test.py",
            "similarity_threshold": 0.99,
            "edits": [{"find": "def hello(): ", "replace": "new", "find_node": None}],
        },
    )

    errors = validator.validate(action, context_paths={"Turn": ["test.py"]})
    assert len(errors) == 1
    assert "The `FIND` block could not be located" in errors[0].message
    assert "Similarity Score" in errors[0].message
    assert "**Similarity Threshold:** 0.99" in errors[0].message


def test_validator_passes_on_successful_fuzzy_match(mock_fs):
    content = "def hello():\n    pass\n"
    mock_fs.read_file.return_value = content
    mock_fs.path_exists.return_value = True

    validator = EditActionValidator(mock_fs, MagicMock())

    # Explicit threshold 0.8 with a minor mismatch
    action = ActionData(
        type="EDIT",
        description="test",
        params={
            "path": "test.py",
            "similarity_threshold": 0.8,
            "edits": [{"find": "def hello(): ", "replace": "new", "find_node": None}],
        },
    )

    errors = validator.validate(action, context_paths={"Turn": ["test.py"]})
    assert len(errors) == 0
