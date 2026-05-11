import pytest
from unittest.mock import MagicMock
from teddy_executor.core.services.session_pruning_service import SessionPruningService
from teddy_executor.core.domain.models.project_context import (
    ProjectContext,
    ContextItem,
)
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


@pytest.fixture
def mock_config():
    config = MagicMock(spec=IConfigService)
    config.get_setting.side_effect = lambda k, d=None: {
        "auto_pruning.enabled": True,
        "auto_pruning.prune_failure_history": True,
        "auto_pruning.prune_validation_failures": True,
    }.get(k, d)
    return config


@pytest.fixture
def mock_fs():
    return MagicMock(spec=IFileSystemManager)


@pytest.fixture
def service(mock_config, mock_fs):
    return SessionPruningService(mock_config, mock_fs)


def test_prune_handles_padding_mismatch(service, mock_fs):
    # Scenario: Turn 1 failed, Turn 2 is green (Recovery).
    def mock_read(p):
        if "1/plan.md" in p:
            return "🔴"
        if "2/plan.md" in p:
            return "🟢"
        return ""

    mock_fs.read_file.side_effect = mock_read

    items = [
        ContextItem(
            path="1/plan.md",
            scope="Turn",
            selected=True,
            token_count=100,
            git_status="",
        ),
        ContextItem(
            path="2/plan.md",
            scope="Turn",
            selected=True,
            token_count=100,
            git_status="",
        ),
    ]
    context = ProjectContext(
        header="# Context",
        content="Context Content",
        items=items,
        agent_name="pf",
        system_prompt_tokens=0,
        total_window=1000,
    )

    pruned = service.prune(context)

    # Turn 1 should be pruned (Recovery cleanup)
    assert pruned.items[0].selected is False
    assert (
        pruned.items[0].auto_prune_reason
        == "Pruned failure history after successful recovery"
    )
    assert pruned.items[1].selected is True


def test_prune_handles_regex_shadowing(service, mock_fs):
    # Scenario: Path contains numeric segment '2024' before Turn '02'.
    # Turn 01 failed, Turn 02 green (Recovery).
    def mock_read(p):
        if "01/plan.md" in p:
            return "🔴"
        if "02/plan.md" in p:
            return "🟢"
        return ""

    mock_fs.read_file.side_effect = mock_read

    items = [
        ContextItem(
            path="projects/2024/sessions/01/plan.md",
            scope="Turn",
            selected=True,
            token_count=100,
            git_status="",
        ),
        ContextItem(
            path="projects/2024/sessions/02/plan.md",
            scope="Turn",
            selected=True,
            token_count=100,
            git_status="",
        ),
    ]
    context = ProjectContext(
        header="# Context",
        content="Context Content",
        items=items,
        agent_name="pf",
        system_prompt_tokens=0,
        total_window=1000,
    )

    pruned = service.prune(context)

    # Turn 01 should be pruned
    assert pruned.items[0].selected is False
    assert "recovery" in pruned.items[0].auto_prune_reason
