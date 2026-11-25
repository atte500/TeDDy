"""Acceptance coverage for wiring the retention batch setting into pruning.

The retention batch is a cadence knob read from ``auto_pruning.retention_batch``.
This tracer bullet proves the outermost pruning entry point reads that setting
through the real configuration adapter, while the value does not yet reshape the
window: a batch of one keeps today's per-turn cadence. The batched window itself
is exercised by the Core deliverable.
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


def test_prune_reads_the_retention_batch_and_keeps_the_per_turn_cadence(tmp_path):
    """
    Given ``retention_batch: 1`` and ``max_turns_retention: 2``
    And four consecutive turns in the context
    When pruning runs
    Then the batch setting was read from configuration
    And the two turns past the limit are pruned, one turn per boundary crossing
    """
    config_dir = tmp_path / ".teddy"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text(
        "auto_pruning:\n"
        "  enabled: true\n"
        "  turn_context_threshold: 0\n"
        "  max_turns_retention: 2\n"
        "  retention_batch: 1\n",
        encoding="utf-8",
    )
    config = _RecordingConfigAdapter(
        config_path=".teddy/config.yaml", root_dir=str(tmp_path)
    )
    files = LocalFileSystemAdapter(
        edit_simulator=EditSimulator(), root_dir=str(tmp_path)
    )
    service = SessionPruningService(config_service=config, file_system_manager=files)

    context = ProjectContext(items=sequential_turn_context(4), header="", content="")

    result = service.prune(context)

    assert "auto_pruning.retention_batch" in config.reads
    selected = {item.path: item.selected for item in result.items}
    assert selected[turn_path(1)] is False
    assert selected[turn_path(2)] is False
    assert selected[turn_path(3)] is True
    assert selected[turn_path(4)] is True
