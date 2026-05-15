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
        "auto_pruning.prune_failure_history": True,
        "auto_pruning.prune_validation_failures": True,
        "auto_pruning.global_context_threshold": 0,
    }.get(k, d)
    fs = create_autospec(IFileSystemManager, instance=True)
    return SessionPruningService(config, fs)


def test_pruning_handles_windows_path_separators(pruning_service):
    # Arrange: Simulate Turn 1 (Success) and Turn 2 (Failure) using Windows paths
    # Turn 3 is the current turn and is Green, triggering recovery cleanup of Turn 2.
    items = [
        ContextItem(
            path=".teddy\\sessions\\S\\01\\plan.md",
            token_count=100,
            scope="Turn",
            selected=True,
            git_status="",
        ),
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
            path=".teddy\\sessions\\S\\03\\plan.md",
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

    # Mock file contents: Turn 1 Green, Turn 2 Red, Turn 3 Green
    def mock_read(path):
        p = path.replace("\\", "/")
        if "01/plan.md" in p:
            return "- **Status:** SUCCESS 🟢"
        if "02/plan.md" in p:
            return "- **Status:** FAILURE 🔴"
        if "03/plan.md" in p:
            return "- **Status:** SUCCESS 🟢"
        return ""

    pruning_service._file_system_manager.path_exists.return_value = True
    pruning_service._file_system_manager.read_file.side_effect = mock_read

    # Act
    pruned_context = pruning_service.prune(context)

    # Assert
    pruned_items = {item.path: item for item in pruned_context.items}

    # Turn 1 should be selected (Green)
    assert pruned_items[".teddy\\sessions\\S\\01\\plan.md"].selected is True
    # Turn 2 should be pruned (Recovery cleanup of Red turn)
    assert pruned_items[".teddy\\sessions\\S\\02\\plan.md"].selected is False
    assert (
        "Pruned failure history"
        in pruned_items[".teddy\\sessions\\S\\02\\plan.md"].auto_prune_reason
    )
    # Turn 3 is the latest, so it remains selected
    assert pruned_items[".teddy\\sessions\\S\\03\\plan.md"].selected is True


def test_extract_turn_id_is_platform_agnostic(pruning_service):
    assert pruning_service._extract_turn_id(".teddy/sessions/01/plan.md") == "01"
    assert pruning_service._extract_turn_id(".teddy\\sessions\\01\\plan.md") == "01"
    assert pruning_service._extract_turn_id("01\\report.md") == "01"
