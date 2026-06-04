import pytest
from unittest.mock import create_autospec
from teddy_executor.core.services.session_pruning_service import SessionPruningService
from teddy_executor.core.domain.models import ProjectContext
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


@pytest.fixture
def mock_config():
    service = create_autospec(IConfigService, instance=True)
    service.get_setting.side_effect = lambda key, default=None: {
        "auto_pruning.enabled": True,
        "auto_pruning.global_context_threshold": 10000,
        "auto_pruning.prune_failure_history": True,
        "auto_pruning.prune_validation_failures": True,
        "auto_pruning.max_turns_retention": 25,
    }.get(key, default)
    return service


@pytest.fixture
def mock_fs():
    mock = create_autospec(IFileSystemManager, instance=True)
    mock.path_exists.return_value = True
    mock.read_file.return_value = ""
    return mock


@pytest.fixture
def service(mock_config, mock_fs):
    return SessionPruningService(
        config_service=mock_config,
        file_system_manager=mock_fs,
    )


def test_prune_accepts_current_status(service):
    """
    Contract: Verify that the prune method accepts the current_status argument.
    """
    # Arrange
    context = ProjectContext(items=[], header="", content="")

    # Act & Assert (Should not raise TypeError)
    service.prune(context, current_status="SUCCESS 🟢")


def test_prune_triggers_recovery_cleanup_via_current_status(service, mock_fs):
    """
    Logic: If current_status is Green, it should trigger pruning of preceding failures.
    """
    # Arrange
    from teddy_executor.core.domain.models.project_context import ContextItem

    # Use standard turn directory names (digits only) to match extraction logic
    items = [
        ContextItem(path="01/plan.md", scope="Turn", token_count=100, git_status=" "),
        ContextItem(path="01/report.md", scope="Turn", token_count=100, git_status=" "),
    ]
    context = ProjectContext(items=items, header="", content="")

    # Mock file content to indicate Turn 01 was a failure
    def mock_read(path):
        if "01/plan.md" in path:
            return "- **Status:** Execution Failed 🔴"
        return ""

    mock_fs.read_file.side_effect = mock_read

    # Act
    # We simulate that the 'current' turn (not yet on disk) is Green
    result = service.prune(context, current_status="SUCCESS 🟢")

    # Assert
    pruned_paths = [i.path for i in result.items if not i.selected]
    assert "01/plan.md" in pruned_paths
    assert "01/report.md" in pruned_paths
    assert (
        result.items[0].auto_prune_reason
        == "Pruned failure history after successful recovery"
    )


def test_global_budget_includes_all_selected_tokens_and_system_prompt(
    service, mock_config
):
    """
    Logic: The global token summation must include selected files from Turn and Session
    scopes (system prompt excluded). Only Turn-scope files are eligible for pruning.
    Session files are never pruned.
    """
    from teddy_executor.core.domain.models.project_context import ContextItem

    # Override threshold to 5000 for this test to trigger pruning.
    # Turn-scope items: 4000 (history) + 2000 (turn) = 6000
    # Session-scope item: 2000
    # Total selected = 8000 > threshold of 5000 → pruning triggered.
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "auto_pruning.enabled": True,
        "auto_pruning.global_context_threshold": 5000,
        "auto_pruning.prune_failure_history": True,
        "auto_pruning.prune_validation_failures": True,
        "auto_pruning.max_turns_retention": 25,
    }.get(key, default)
    items = [
        ContextItem(
            path="src/login.py", scope="Session", token_count=2000, git_status=" "
        ),
        ContextItem(
            path=".teddy/sessions/S/01/plan.md",
            scope="Turn",
            token_count=4000,
            git_status=" ",
        ),
        ContextItem(path="02/plan.md", scope="Turn", token_count=2000, git_status=" "),
    ]
    context = ProjectContext(
        items=items,
        header="",
        content="",
        system_prompt_tokens=3000,
    )

    # Act
    result = service.prune(context)

    # Assert
    # The largest prunable candidate (Turn 1 Plan / History file with 4000 tokens) must be pruned first.
    # This reduces total tokens from 8000 to 4000, which is below the 5000 threshold.
    # Therefore, turn_items (2000 tokens) should remain selected.
    history_item = next(i for i in result.items if "01/plan.md" in i.path)
    turn_item = next(i for i in result.items if "02/plan.md" in i.path)
    session_item = next(i for i in result.items if "src/login.py" in i.path)

    assert history_item.selected is False
    assert history_item.auto_prune_reason == "Pruned to fit context budget"
    assert turn_item.selected is True
    assert session_item.selected is True


def test_global_budget_strictly_protects_initial_request(service, mock_config):
    """
    Logic: Even if initial_request.md is extremely large and we exceed the global budget,
    it must be protected and never pruned.
    """
    from teddy_executor.core.domain.models.project_context import ContextItem

    # Total threshold = 10000.
    # Initial request (History path) = 8000 tokens. (Must NOT be pruned!)
    # Turn file = 4000 tokens. (Eligible to prune!)
    # System prompt = 1000 tokens.
    # Total selected = 8000 + 4000 + 1000 = 13000 > 10000 threshold.
    items = [
        ContextItem(
            path=".teddy/sessions/S/initial_request.md",
            scope="Session",
            token_count=8000,
            git_status=" ",
        ),
        ContextItem(path="02/plan.md", scope="Turn", token_count=4000, git_status=" "),
    ]
    context = ProjectContext(
        items=items,
        header="",
        content="",
        system_prompt_tokens=1000,
    )

    # Act
    result = service.prune(context)

    # Assert
    init_req_item = next(i for i in result.items if "initial_request.md" in i.path)
    turn_item = next(i for i in result.items if "02/plan.md" in i.path)

    # Turn item is pruned to bring total selected to 13000 - 4000 = 9000 <= 10000
    assert init_req_item.selected is True
    assert turn_item.selected is False
    assert turn_item.auto_prune_reason == "Pruned to fit context budget"
