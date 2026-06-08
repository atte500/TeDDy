import pytest
from unittest.mock import create_autospec
from teddy_executor.core.services.session_pruning_service import SessionPruningService
from teddy_executor.core.domain.models import ProjectContext
from teddy_executor.core.domain.models.project_context import ContextItem
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


@pytest.fixture
def mock_config():
    service = create_autospec(IConfigService, instance=True)
    service.get_setting.side_effect = lambda key, default=None: {
        "auto_pruning.enabled": True,
        "auto_pruning.prune_failure_history": True,
        "auto_pruning.prune_validation_failures": True,
    }.get(key, default)
    return service


@pytest.fixture
def mock_fs():
    return create_autospec(IFileSystemManager, instance=True)


@pytest.fixture
def service(mock_config, mock_fs):
    return SessionPruningService(
        config_service=mock_config, file_system_manager=mock_fs
    )


def test_prune_ignores_emoji_in_rationale(service, mock_fs):
    """
    Logic: Ensure that 🔴 in rationale does not trigger pruning if the Status line is 🟢.
    """
    # Arrange
    items = [
        ContextItem(path="01/plan.md", scope="Turn", token_count=100, git_status=" "),
    ]
    context = ProjectContext(items=items, header="", content="")

    # Plan has a 🔴 in rationale but 🟢 in status
    content = (
        "# Plan\n"
        "## Rationale\n"
        "I found a bug 🔴 but I fixed it.\n"
        "\n"
        "- **Status:** SUCCESS 🟢"
    )
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = content

    # Act
    # Recovery cleanup is triggered by current status being green
    result = service.prune(context, current_status="SUCCESS 🟢")

    # Assert
    # Turn 01 should NOT be pruned because it is actually green
    assert result.items[0].selected is True


def test_prune_targets_anchored_status_failure(service, mock_fs):
    """
    Logic: Ensure that 🔴 in the Status line correctly triggers pruning.
    """
    # Arrange
    items = [
        ContextItem(path="01/plan.md", scope="Turn", token_count=100, git_status=" "),
    ]
    context = ProjectContext(items=items, header="", content="")

    content = "# Plan\n- **Status:** FAILED 🔴"
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = content

    # Act
    result = service.prune(context, current_status="SUCCESS 🟢")

    # Assert
    assert result.items[0].selected is False
    assert (
        result.items[0].auto_prune_reason
        == "Pruned failure history after successful recovery"
    )


def test_prune_targets_anchored_validation_failure(service, mock_fs):
    """
    Logic: Ensure that report validation failure requires the specific anchored line.
    """
    # Arrange
    items = [
        ContextItem(path="01/report.md", scope="Turn", token_count=100, git_status=" "),
    ]
    context = ProjectContext(items=items, header="", content="")

    # Valid report with "Validation Failed" in a note, but not in status
    content = (
        "# Report\n"
        "Note: We previously had a Validation Failed error.\n"
        "- **Overall Status:** SUCCESS"
    )
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = content

    # Act
    result = service.prune(context)

    # Assert
    assert result.items[0].selected is True


def test_validation_failure_without_non_vf_report_is_preserved(service, mock_fs):
    """
    Heuristic 4: Validation failure without any non-VF report on disk
    should be preserved (not pruned).
    """
    # Arrange
    items = [
        ContextItem(path="01/report.md", scope="Turn", token_count=100, git_status=" "),
    ]
    context = ProjectContext(items=items, header="", content="")

    content = "- **Overall Status:** Validation Failed"
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = content

    # Act: current_status is "Validation Failed" so no non-VF anchor
    result = service.prune(context, current_status="Validation Failed")

    # Assert: turn should be preserved because no non-VF report exists
    assert result.items[0].selected is True


def test_validation_failure_with_non_vf_report_is_pruned(service, mock_fs):
    """
    Heuristic 4: Validation failure with a subsequent non-VF report on disk
    should be pruned.
    """
    # Arrange
    items = [
        ContextItem(path="01/report.md", scope="Turn", token_count=100, git_status=" "),
        ContextItem(path="02/report.md", scope="Turn", token_count=100, git_status=" "),
    ]
    context = ProjectContext(items=items, header="", content="")

    def read_file_side_effect(path: str) -> str:
        if "01/report.md" in path:
            return "- **Overall Status:** Validation Failed"
        elif "02/report.md" in path:
            return "- **Overall Status:** SUCCESS"
        return ""

    mock_fs.path_exists.return_value = True
    mock_fs.read_file.side_effect = read_file_side_effect

    # Act: current_status is "Validation Failed" but disk has non-VF report on turn 02
    result = service.prune(context, current_status="Validation Failed")

    # Assert: turn 01 (VF) should be pruned; turn 02 (non-VF) preserved
    assert result.items[0].selected is False
    assert result.items[1].selected is True


def test_non_vf_report_before_vf_turn_does_not_trigger_pruning(service, mock_fs):
    """
    Edge case: A non-VF report before a VF turn should NOT trigger pruning.
    Only VF turns before the latest non-VF report are pruned.
    """
    # Arrange
    items = [
        ContextItem(path="01/report.md", scope="Turn", token_count=100, git_status=" "),
        ContextItem(path="02/report.md", scope="Turn", token_count=100, git_status=" "),
    ]
    context = ProjectContext(items=items, header="", content="")

    # Turn 01 has SUCCESS (non-VF), turn 02 has Validation Failed (VF)
    def read_file_side_effect(path: str) -> str:
        if "01/report.md" in path:
            return "- **Overall Status:** SUCCESS"
        elif "02/report.md" in path:
            return "- **Overall Status:** Validation Failed"
        return ""

    mock_fs.path_exists.return_value = True
    mock_fs.read_file.side_effect = read_file_side_effect

    # Act: current_status is "Validation Failed" (no current non-VF anchor)
    result = service.prune(context, current_status="Validation Failed")

    # Assert: both turns should be preserved.
    # Turn 01 is not a VF, so Heuristic 4 ignores it.
    # Turn 02 is a VF but the only non-VF report (turn 01) is before it,
    # so the guard does not prune it.
    assert result.items[0].selected is True
    assert result.items[1].selected is True
