"""Unit tests: turn-meta load/save seam on SessionService.

Drives the non-breaking seam expansion exposing repository-backed
turn-meta persistence as public methods on `SessionService`, so core
consumers (e.g., the pipeline MESSAGE suppression path) persist metadata
via Constructor-Injected dependencies without hand-rolled yaml handling
or direct repository access. The public API is symmetric (both methods
take the turn directory); the filename asymmetry of the underlying
repository contract stays encapsulated behind the seam.
"""

from typing import cast
from unittest.mock import Mock

import pytest

from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.ports.outbound.session_repository import ISessionRepository
from teddy_executor.core.ports.outbound.time_service import ITimeService
from teddy_executor.core.services.session_repository import SessionRepository
from teddy_executor.core.services.session_service import SessionService


class InMemoryFileSystem:
    """Minimal dict-backed IFileSystemManager fake (scoped to file I/O)."""

    def __init__(self) -> None:
        self._files: dict[str, str] = {}

    def path_exists(self, path: str) -> bool:
        return path in self._files

    def read_file(self, path: str) -> str:
        return self._files[path]

    def write_file(self, path: str, content: str) -> None:
        self._files[path] = content


TURN_DIR = ".teddy/sessions/20260417_120000-feature/01"


@pytest.fixture
def turn_repository() -> ISessionRepository:
    """A REAL SessionRepository over an in-memory filesystem fake.

    Using the real repository keeps the seam test end-to-end honest for
    the meta surface (true yaml round-trip) while remaining in-memory.
    SessionRepository IS an ISessionRepository, so the repository
    Constructor Injection is Mypy-clean; the filesystem fake satisfies
    the wide IFileSystemManager protocol via an explicit cast at
    construction (it deliberately implements only the file-I/O surface
    the meta load/save path exercises).
    """
    fs = cast(IFileSystemManager, InMemoryFileSystem())
    return SessionRepository(fs)


@pytest.fixture
def service(turn_repository: ISessionRepository) -> SessionService:
    """SessionService with the repository Constructor-Injected.

    The remaining constructor dependencies are inert for the turn-meta
    surface under test and are therefore strictly spec-bound mocks (no
    bare MagicMock; no behavior is asserted against them).
    """
    return SessionService(
        file_system_manager=Mock(spec=IFileSystemManager),
        repository=turn_repository,
        time_service=Mock(spec=ITimeService),
        prompt_manager=Mock(spec=IPromptManager),
        init_service=Mock(spec=IInitUseCase),
        config_service=Mock(spec=IConfigService),
    )


def test_save_turn_meta_persists_through_injected_repository(
    service: SessionService, turn_repository: ISessionRepository
) -> None:
    # Arrange
    meta = {"agent_name": "assistant", "turn_cost": 0.5}

    # Act
    service.save_turn_meta(TURN_DIR, meta)

    # Assert: readable through the raw repository contract (same file)
    assert turn_repository.load_meta(TURN_DIR) == meta


def test_load_turn_meta_reads_through_injected_repository(
    service: SessionService, turn_repository: ISessionRepository
) -> None:
    # Arrange
    turn_repository.save_meta(f"{TURN_DIR}/meta.yaml", {"agent_name": "assistant"})

    # Act
    loaded = service.load_turn_meta(TURN_DIR)

    # Assert
    assert loaded == {"agent_name": "assistant"}


def test_awaiting_reply_flag_round_trips_through_service_seam(
    service: SessionService,
) -> None:
    # Arrange: the exact consumer scenario of the pipeline suppression path
    meta = {"agent_name": "assistant"}

    # Act
    service.save_turn_meta(TURN_DIR, {**meta, "awaiting_reply": True})
    loaded = service.load_turn_meta(TURN_DIR)

    # Assert
    assert loaded["awaiting_reply"] is True
