import pytest
from unittest.mock import create_autospec
from teddy_executor.core.services.session_pruning_service import SessionPruningService
from teddy_executor.core.domain.models.project_context import (
    ProjectContext,
    ContextItem,
)
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


@pytest.fixture
def mock_config():
    config = create_autospec(IConfigService, instance=True)
    config.get_setting.side_effect = lambda k, d=None: {
        "auto_pruning.enabled": True,
        "auto_pruning.prune_validation_failures": True,
    }.get(k, d)
    return config


@pytest.fixture
def mock_fs():
    return create_autospec(IFileSystemManager, instance=True)


@pytest.fixture
def service(mock_config, mock_fs):
    return SessionPruningService(mock_config, mock_fs)


def test_prune_matches_a_padded_turn_directory(service, mock_fs):
    """A zero-padded directory matches the unpadded id the heuristic keys on.

    The validation heuristic stores its victims under ``str(int(turn_id))``, so
    a ``01/`` directory only matches through that normalisation.
    """

    # Scenario: Turn 01 failed validation and Turn 02 succeeded afterwards.
    def mock_read(p):
        if "01/report.md" in p:
            return "- **Overall Status:** Validation Failed"
        if "02/report.md" in p:
            return "- **Overall Status:** SUCCESS"
        return ""

    mock_fs.path_exists.return_value = True
    mock_fs.read_file.side_effect = mock_read

    items = [
        ContextItem(
            path="01/report.md",
            scope="Turn",
            selected=True,
            token_count=100,
            git_status="",
        ),
        ContextItem(
            path="02/report.md",
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

    assert pruned.items[0].selected is False
    assert pruned.items[0].auto_prune_reason == "Plan failed validation"
    assert pruned.items[1].selected is True


def test_prune_ignores_a_year_segment_before_the_turn_directory(service, mock_fs):
    """A four-digit year segment is not a turn id, so matching starts at ``01``."""

    # Scenario: the path carries '2024' ahead of the turn directories.
    def mock_read(p):
        if "01/report.md" in p:
            return "- **Overall Status:** Validation Failed"
        if "02/report.md" in p:
            return "- **Overall Status:** SUCCESS"
        return ""

    mock_fs.path_exists.return_value = True
    mock_fs.read_file.side_effect = mock_read

    items = [
        ContextItem(
            path="projects/2024/sessions/01/report.md",
            scope="Turn",
            selected=True,
            token_count=100,
            git_status="",
        ),
        ContextItem(
            path="projects/2024/sessions/02/report.md",
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

    assert pruned.items[0].selected is False
    assert pruned.items[0].auto_prune_reason == "Plan failed validation"
    assert pruned.items[1].selected is True
