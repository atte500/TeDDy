"""Core: plan preservation reads the full plan, not the READ-capped view.

A plan whose ``## Message`` section falls beyond ``read.max_lines`` (default
1000) must still be detected, because plan correctness reads route through
``read_raw_file`` instead of the truncating ``read_file``. The test drives the
real ``LocalFileSystemAdapter`` so the truncation is modeled faithfully.
"""

from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)
from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.ports.outbound.session_repository import ISessionRepository
from teddy_executor.core.ports.outbound.time_service import ITimeService
from teddy_executor.core.services.edit_simulator import EditSimulator
from teddy_executor.core.services.session_service import SessionService
from tests.harness.setup.mocking import register_mock


def _service_with_real_filesystem(container, root: str) -> SessionService:
    """Build a SessionService backed by the real filesystem adapter at ``root``."""
    file_system = LocalFileSystemAdapter(
        edit_simulator=EditSimulator(), root_dir=root, max_read_lines=1000
    )
    return SessionService(
        file_system_manager=file_system,
        repository=register_mock(container, ISessionRepository),
        time_service=register_mock(container, ITimeService),
        prompt_manager=register_mock(container, IPromptManager),
        init_service=register_mock(container, IInitUseCase),
        config_service=register_mock(container, IConfigService),
    )


def test_message_marker_beyond_the_read_cap_is_preserved(tmp_path, container):
    turn_dir = tmp_path / "01"
    turn_dir.mkdir()
    body = ["# Plan", "## Action Plan", ""]
    body += [f"- filler line {i}" for i in range(1, 1201)]
    body += ["## Message", "Please review the above."]
    (turn_dir / "plan.md").write_text("\n".join(body) + "\n", encoding="utf-8")

    service = _service_with_real_filesystem(container, str(tmp_path))

    assert service._is_preserved_turn(turn_dir) is True
