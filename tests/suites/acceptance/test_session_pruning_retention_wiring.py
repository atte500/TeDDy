"""Acceptance coverage for the retention ceiling.

``auto_pruning.max_turns_retention`` is a ceiling on how many turns the
turn-scoped history may hold, and ``auto_pruning.retention_batch`` is how many
of the oldest turns fall together once the ceiling is exceeded. This tracer
bullet drives the outermost pruning entry point over the real configuration and
file-system adapters, so both settings are read from a real ``config.yaml`` and
the ceiling is enforced at the boundary.
"""

from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)
from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter
from teddy_executor.core.domain.models.project_context import ProjectContext
from teddy_executor.core.services.edit_simulator import EditSimulator
from teddy_executor.core.services.session_pruning_service import SessionPruningService
from tests.harness.setup.pruning_scenarios import sequential_turn_context, turn_path


class _RecordingConfigAdapter(YamlConfigAdapter):
    """The real config adapter, recording which keys pruning reads."""

    def __init__(self, config_path: str, root_dir: str):
        self.reads: list[str] = []
        super().__init__(config_path=config_path, root_dir=root_dir)

    def get_setting(self, key, default=None):
        self.reads.append(key)
        return super().get_setting(key, default)


def _prune_with(tmp_path, *, limit: int, batch: int, turn_count: int):
    """Drive ``prune()`` over a real config and file system in ``tmp_path``."""
    config_dir = tmp_path / ".teddy"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text(
        "auto_pruning:\n"
        "  enabled: true\n"
        "  turn_context_threshold: 0\n"
        f"  max_turns_retention: {limit}\n"
        f"  retention_batch: {batch}\n",
        encoding="utf-8",
    )
    config = _RecordingConfigAdapter(
        config_path=".teddy/config.yaml", root_dir=str(tmp_path)
    )
    files = LocalFileSystemAdapter(
        edit_simulator=EditSimulator(), root_dir=str(tmp_path)
    )
    service = SessionPruningService(config_service=config, file_system_manager=files)
    context = ProjectContext(
        items=sequential_turn_context(turn_count), header="", content=""
    )
    return service.prune(context), config


def test_a_turn_past_the_ceiling_drops_a_batch_of_the_oldest_turns(tmp_path):
    """
    Given ``max_turns_retention: 4`` and ``retention_batch: 2``
    And five consecutive turns in the context
    When pruning runs
    Then both settings were read from configuration
    And the two oldest turns are dropped together, keeping the three newest
    """
    result, config = _prune_with(tmp_path, limit=4, batch=2, turn_count=5)

    assert "auto_pruning.max_turns_retention" in config.reads
    assert "auto_pruning.retention_batch" in config.reads
    selected = {item.path: item.selected for item in result.items}
    assert [selected[turn_path(turn_id)] for turn_id in range(1, 6)] == [
        False,
        False,
        True,
        True,
        True,
    ]
    reasons = {item.auto_prune_reason for item in result.items if not item.selected}
    assert reasons == {"Turn exceeds retention limit of 4"}


def test_a_batch_of_one_keeps_the_per_turn_cadence(tmp_path):
    """
    Given ``max_turns_retention: 4`` and ``retention_batch: 1``
    And five consecutive turns in the context
    When pruning runs
    Then exactly the oldest turn is dropped
    """
    result, _ = _prune_with(tmp_path, limit=4, batch=1, turn_count=5)

    selected = {item.path: item.selected for item in result.items}
    assert [selected[turn_path(turn_id)] for turn_id in range(1, 6)] == [
        False,
        True,
        True,
        True,
        True,
    ]
