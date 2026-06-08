"""Integration tests for validation failure pruning timing (Slice 02-13).

Verifies the end-to-end wiring of Heuristic 4's non-VF report guard through
the SessionPruningService with mocked file system and config dependencies.
"""

from unittest.mock import create_autospec

from teddy_executor.core.services.session_pruning_service import (
    SessionPruningService,
)
from teddy_executor.core.domain.models import ProjectContext
from teddy_executor.core.domain.models.project_context import ContextItem
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


def test_validation_failure_pruned_based_on_non_vf_report_anchor(container):
    """
    Integration: Heuristic 4 guard wiring through SessionPruningService.

    Verifies that:
    1. Validation failure without non-VF report is preserved.
    2. Validation failure with non-VF current_status is pruned.
    """
    # Arrange: Register config with validation pruning enabled
    mock_config = create_autospec(IConfigService, instance=True)
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "auto_pruning.enabled": True,
        "auto_pruning.prune_failure_history": False,  # Isolate Heuristic 4
        "auto_pruning.prune_validation_failures": True,  # Enable VF pruning
        "auto_pruning.preserve_message_turns": False,  # No message sparing
    }.get(key, default)

    mock_fs = create_autospec(IFileSystemManager, instance=True)

    # Override container registrations to use our mocks
    container.register(IConfigService, instance=mock_config)
    container.register(IFileSystemManager, instance=mock_fs)

    service = container.resolve(SessionPruningService)

    # --- Scenario 1: No non-VF anchor → VF preserved ---
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "- **Overall Status:** Validation Failed"

    items = [
        ContextItem(path="01/report.md", scope="Turn", token_count=100, git_status=" "),
    ]
    context = ProjectContext(items=items, header="", content="")

    # Act: current_status is "Validation Failed" → no non-VF anchor
    result = service.prune(context, current_status="Validation Failed")

    # Assert: VF turn preserved
    assert result.items[0].selected is True, (
        "VF turn should be preserved when no non-VF report exists"
    )

    # --- Scenario 2: Non-VF current_status → VF pruned ---
    result = service.prune(context, current_status="SUCCESS")

    # Assert: VF turn pruned because current_status is non-VF
    assert result.items[0].selected is False, (
        "VF turn should be pruned when current_status is non-VF"
    )
    assert result.items[0].auto_prune_reason == "Plan failed validation", (
        "Prune reason should indicate validation failure"
    )


def test_validation_failure_pruned_by_disk_non_vf_report(container):
    """
    Integration: VF turn pruned when a later turn has a non-VF report on disk.
    """
    # Arrange
    mock_config = create_autospec(IConfigService, instance=True)
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "auto_pruning.enabled": True,
        "auto_pruning.prune_failure_history": False,
        "auto_pruning.prune_validation_failures": True,
        "auto_pruning.preserve_message_turns": False,
    }.get(key, default)

    mock_fs = create_autospec(IFileSystemManager, instance=True)

    # Turn 01: VF report, Turn 02: non-VF report (SUCCESS)
    def read_file_side_effect(path: str) -> str:
        if "01/report.md" in path:
            return "- **Overall Status:** Validation Failed"
        elif "02/report.md" in path:
            return "- **Overall Status:** SUCCESS"
        return ""

    mock_fs.path_exists.return_value = True
    mock_fs.read_file.side_effect = read_file_side_effect

    container.register(IConfigService, instance=mock_config)
    container.register(IFileSystemManager, instance=mock_fs)

    service = container.resolve(SessionPruningService)

    items = [
        ContextItem(path="01/report.md", scope="Turn", token_count=100, git_status=" "),
        ContextItem(path="02/report.md", scope="Turn", token_count=100, git_status=" "),
    ]
    context = ProjectContext(items=items, header="", content="")

    # Act: current_status is VF, but disk has non-VF report on turn 02
    result = service.prune(context, current_status="Validation Failed")

    # Assert: turn 01 pruned, turn 02 preserved
    assert result.items[0].selected is False, "VF turn 01 should be pruned"
    assert result.items[0].auto_prune_reason == "Plan failed validation"
    assert result.items[1].selected is True, "Non-VF turn 02 should be preserved"


def test_vf_chain_without_anchor_all_preserved(container):
    """
    Integration: Multiple consecutive VF turns without non-VF anchor → all preserved.
    """
    # Arrange
    mock_config = create_autospec(IConfigService, instance=True)
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "auto_pruning.enabled": True,
        "auto_pruning.prune_failure_history": False,
        "auto_pruning.prune_validation_failures": True,
        "auto_pruning.preserve_message_turns": False,
    }.get(key, default)

    mock_fs = create_autospec(IFileSystemManager, instance=True)
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "- **Overall Status:** Validation Failed"

    container.register(IConfigService, instance=mock_config)
    container.register(IFileSystemManager, instance=mock_fs)

    service = container.resolve(SessionPruningService)

    items = [
        ContextItem(path="01/report.md", scope="Turn", token_count=100, git_status=" "),
        ContextItem(path="02/report.md", scope="Turn", token_count=100, git_status=" "),
        ContextItem(path="03/report.md", scope="Turn", token_count=100, git_status=" "),
    ]
    context = ProjectContext(items=items, header="", content="")

    # Act: all VF, current_status is VF → no anchor
    result = service.prune(context, current_status="Validation Failed")

    # Assert: all preserved
    for i in range(3):
        assert result.items[i].selected is True, (
            f"VF turn {i + 1:02d} should be preserved in chain without anchor"
        )
