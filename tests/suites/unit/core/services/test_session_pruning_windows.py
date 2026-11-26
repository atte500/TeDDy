import pytest
from unittest.mock import create_autospec
from teddy_executor.core.services.session_pruning_service import SessionPruningService
from teddy_executor.core.domain.models.project_context import (
    ProjectContext,
    ContextItem,
)


@pytest.fixture
def pruning_service():
    from teddy_executor.core.ports.outbound.config_service import IConfigService
    from teddy_executor.core.ports.outbound.file_system_manager import (
        IFileSystemManager,
    )

    config = create_autospec(IConfigService, instance=True)
    # Enable all pruning heuristics
    config.get_setting.side_effect = lambda k, d=None: {
        "auto_pruning.enabled": True,
        "auto_pruning.prune_validation_failures": True,
        "auto_pruning.turn_context_threshold": 0,
    }.get(k, d)
    fs = create_autospec(IFileSystemManager, instance=True)
    return SessionPruningService(config, fs)


def test_pruning_handles_windows_path_separators(pruning_service):
    """A backslash path prunes a validation-failed turn once a later turn succeeds."""
    # Arrange: Turn 02 failed validation and Turn 03 succeeded afterwards.
    items = [
        ContextItem(
            path=".teddy\\sessions\\S\\01\\report.md",
            token_count=100,
            scope="Turn",
            selected=True,
            git_status="",
        ),
        ContextItem(
            path=".teddy\\sessions\\S\\02\\plan.md",
            token_count=100,
            scope="Turn",
            selected=True,
            git_status="",
        ),
        ContextItem(
            path=".teddy\\sessions\\S\\02\\report.md",
            token_count=100,
            scope="Turn",
            selected=True,
            git_status="",
        ),
        ContextItem(
            path=".teddy\\sessions\\S\\03\\report.md",
            token_count=100,
            scope="Turn",
            selected=True,
            git_status="",
        ),
    ]
    context = ProjectContext(
        header="H",
        content="C",
        items=items,
        agent_name="A",
        system_prompt_tokens=0,
        total_window=0,
    )

    # Mock file contents: Turn 01 and Turn 03 succeeded, Turn 02 failed validation.
    def mock_read(path):
        p = path.replace("\\", "/")
        if "01/report.md" in p:
            return "- **Overall Status:** SUCCESS"
        if "02/report.md" in p:
            return "- **Overall Status:** Validation Failed"
        if "03/report.md" in p:
            return "- **Overall Status:** SUCCESS"
        return ""

    pruning_service._file_system_manager.path_exists.return_value = True
    pruning_service._file_system_manager.read_file.side_effect = mock_read

    # Act
    pruned_context = pruning_service.prune(context)

    # Assert
    pruned_items = {item.path: item for item in pruned_context.items}

    assert pruned_items[".teddy\\sessions\\S\\01\\report.md"].selected is True
    # The failed turn leaves with both of its records.
    assert pruned_items[".teddy\\sessions\\S\\02\\plan.md"].selected is False
    assert pruned_items[".teddy\\sessions\\S\\02\\report.md"].selected is False
    assert (
        pruned_items[".teddy\\sessions\\S\\02\\report.md"].auto_prune_reason
        == "Plan failed validation"
    )
    assert pruned_items[".teddy\\sessions\\S\\03\\report.md"].selected is True


def test_extract_turn_id_is_platform_agnostic(pruning_service):
    assert pruning_service._extract_turn_id(".teddy/sessions/01/plan.md") == "01"
    assert pruning_service._extract_turn_id(".teddy\\sessions\\01\\plan.md") == "01"
    assert pruning_service._extract_turn_id("01\\report.md") == "01"
