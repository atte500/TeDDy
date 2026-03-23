import pytest
from unittest.mock import MagicMock
from teddy_executor.adapters.inbound.console_plan_reviewer import ConsolePlanReviewer
from teddy_executor.core.domain.models.plan import ActionData
from teddy_executor.core.domain.models import ChangeSet


@pytest.fixture
def mock_interactor():
    return MagicMock()


@pytest.fixture
def mock_file_system():
    return MagicMock()


@pytest.fixture
def mock_config():
    mock = MagicMock()
    mock.get_setting.return_value = 0.95
    return mock


@pytest.fixture
def mock_edit_simulator():
    return MagicMock()


@pytest.fixture
def reviewer(mock_interactor, mock_file_system, mock_config, mock_edit_simulator):
    return ConsolePlanReviewer(
        user_interactor=mock_interactor,
        file_system_manager=mock_file_system,
        config_service=mock_config,
        edit_simulator=mock_edit_simulator,
    )


def test_review_action_generates_correct_prompt_and_changeset_for_create(
    reviewer, mock_interactor, mock_file_system
):
    """Should generate a detailed prompt and a ChangeSet for a CREATE action."""
    mock_interactor.confirm_action.return_value = (True, "")
    mock_file_system.path_exists.return_value = False

    action = ActionData(
        type="CREATE",
        params={"path": "test.txt", "content": "new content"},
        description="Create a test file",
    )

    reviewer.review_action(action, total_actions=1)

    # Verify confirm_action call
    args, kwargs = mock_interactor.confirm_action.call_args
    prompt = kwargs["action_prompt"]
    change_set = kwargs["change_set"]

    assert "Action: CREATE" in prompt
    assert "Description: Create a test file" in prompt
    assert "path: test.txt" in prompt

    assert isinstance(change_set, ChangeSet)
    assert change_set.action_type == "CREATE"
    assert change_set.after_content == "new content"


def test_review_action_generates_changeset_for_edit(
    reviewer, mock_interactor, mock_file_system, mock_edit_simulator
):
    """Should generate a ChangeSet using the edit simulator for an EDIT action."""
    mock_interactor.confirm_action.return_value = (True, "")
    mock_file_system.path_exists.return_value = True
    mock_file_system.read_file.return_value = "old content"
    mock_edit_simulator.simulate_edits.return_value = ("simulated content", 1.0)

    action = ActionData(
        type="EDIT",
        params={"path": "test.txt", "edits": []},
        description="Edit a test file",
    )

    reviewer.review_action(action, total_actions=1)

    args, kwargs = mock_interactor.confirm_action.call_args
    change_set = kwargs["change_set"]

    assert isinstance(change_set, ChangeSet)
    assert change_set.action_type == "EDIT"
    assert change_set.before_content == "old content"
    assert change_set.after_content == "simulated content"
    mock_edit_simulator.simulate_edits.assert_called_once()


def test_review_action_returns_false_on_denial(reviewer, mock_interactor):
    """Should return False and deselect action if the user denies."""
    mock_interactor.confirm_action.return_value = (False, "Reason")
    action = ActionData(type="CREATE", params={"path": "test.txt"}, description="Test")

    result = reviewer.review_action(action, total_actions=1)

    assert result is False
    assert action.selected is False


def test_review_action_no_changeset_for_research(reviewer, mock_interactor):
    """Should not generate a ChangeSet for a RESEARCH action."""
    mock_interactor.confirm_action.return_value = (True, "")

    action = ActionData(
        type="RESEARCH", params={"queries": ["query 1"]}, description="Search for info"
    )

    reviewer.review_action(action, total_actions=1)

    args, kwargs = mock_interactor.confirm_action.call_args
    assert kwargs["change_set"] is None
    assert "Action: RESEARCH" in kwargs["action_prompt"]
