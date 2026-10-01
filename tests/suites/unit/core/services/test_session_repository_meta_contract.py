"""Contract tests: `awaiting_reply` flag round-trip through session turn meta.

Characterization contract pinning the generic yaml round-trip behavior of
`SessionRepository.save_meta`/`load_meta` for the `awaiting_reply` boolean
flag. The asymmetric signatures are deliberate and pinned here:
`load_meta(turn_dir)` appends "/meta.yaml", while `save_meta(path, data)`
takes the full file path.
"""

import pytest

from teddy_executor.core.services.session_repository import SessionRepository


class InMemoryFileSystem:
    """Minimal in-memory IFileSystemManager fake (dict-backed file store)."""

    def __init__(self) -> None:
        self._files: dict[str, str] = {}

    def path_exists(self, path: str) -> bool:
        return path in self._files

    def read_file(self, path: str) -> str:
        return self._files[path]

    def write_file(self, path: str, content: str) -> None:
        self._files[path] = content

    # Unused port methods are intentionally absent: this fake is scoped to
    # the meta load/save surface exercised by these contract tests.


@pytest.fixture
def repository() -> SessionRepository:
    return SessionRepository(InMemoryFileSystem())


@pytest.mark.parametrize("flag", [True, False])
def test_awaiting_reply_flag_round_trips_through_meta(
    repository: SessionRepository, flag: bool
) -> None:
    # Arrange
    turn_dir = ".teddy/sessions/20260417_120000-feature/01"
    meta = {"agent_name": "assistant", "awaiting_reply": flag}

    # Act
    repository.save_meta(f"{turn_dir}/meta.yaml", meta)
    loaded = repository.load_meta(turn_dir)

    # Assert: the boolean survives serialization; the load path targets
    # "<turn_dir>/meta.yaml" (same file the save wrote).
    assert loaded["awaiting_reply"] is flag


def test_meta_without_awaiting_reply_flag_loads_falsy(
    repository: SessionRepository,
) -> None:
    # Arrange
    turn_dir = ".teddy/sessions/20260417_120000-feature/01"
    repository.save_meta(f"{turn_dir}/meta.yaml", {"agent_name": "assistant"})

    # Act
    loaded = repository.load_meta(turn_dir)

    # Assert: an absent flag reads falsy — the state machine treats this
    # as "not awaiting a reply".
    assert not loaded.get("awaiting_reply")
