"""Unit: SessionService persists the CANONICAL agent name to meta.yaml.

Item 6 (session-behaviour): the agent name written to turn metadata must be
the canonical form (first letter uppercase, remainder lowercase), so
``teddy start -a PATHFINDER`` persists ``agent_name: Pathfinder``. The planning
header (``Waiting for Pathfinder to respond...``) reads this persisted value
directly, so canonicalising it here fixes the header without any
planning-service change.
"""

from datetime import datetime, timezone

import pytest

from tests.harness.setup.mocking import register_mock
from teddy_executor.core.domain.models.session import SessionOptions
from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.ports.outbound.session_repository import ISessionRepository
from teddy_executor.core.ports.outbound.time_service import ITimeService
from teddy_executor.core.services.session_service import SessionService

_CASES = [
    ("PATHFINDER", "Pathfinder"),
    ("pathfinder", "Pathfinder"),
    ("DeVeLoPeR", "Developer"),
]


def _make_service(container):
    """Builds a SessionService with fully mocked ports and a frozen clock."""
    fs = register_mock(container, IFileSystemManager)
    repo = register_mock(container, ISessionRepository)
    time_service = register_mock(container, ITimeService)
    prompts = register_mock(container, IPromptManager)
    init = register_mock(container, IInitUseCase)
    config = register_mock(container, IConfigService)

    now = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
    time_service.now.return_value = now
    time_service.now_utc.return_value = now
    config.get_setting.return_value = True
    init.ensure_initialized.return_value = None

    service = SessionService(
        file_system_manager=fs,
        repository=repo,
        time_service=time_service,
        prompt_manager=prompts,
        init_service=init,
        config_service=config,
    )
    return service, fs, repo, prompts


@pytest.mark.parametrize(("raw_agent", "expected_agent"), _CASES)
def test_create_session_persists_canonical_agent_name(
    container, raw_agent, expected_agent
):
    """``create_session`` writes the canonical agent name into meta.yaml."""
    service, fs, repo, prompts = _make_service(container)

    fs.create_directory_exclusive.return_value = True
    fs.path_exists.side_effect = lambda p: (
        p
        in (
            ".teddy/prompts",
            ".teddy/init.context",
        )
    )
    fs.list_directory.side_effect = lambda d: {
        ".teddy/prompts": ["pathfinder.xml", "developer.xml"],
    }.get(d, [])
    fs.read_file.return_value = "README.md"
    prompts.fetch_system_prompt.return_value = "Agent Name: X\n\n<prompt/>"

    service.create_session(SessionOptions(name="casing-check", agent_name=raw_agent))

    persisted = repo.save_meta.call_args.args[1]
    assert persisted["agent_name"] == expected_agent, (
        "meta.yaml must persist the canonical agent name, got "
        f"{persisted['agent_name']!r}"
    )


@pytest.mark.parametrize(("raw_agent", "expected_agent"), _CASES)
def test_set_session_agent_persists_canonical_agent_name(
    container, raw_agent, expected_agent
):
    """``set_session_agent`` writes the canonical agent name into meta.yaml."""
    service, fs, repo, prompts = _make_service(container)

    session_root = ".teddy/sessions/test-casing"
    repo.get_latest_turn.return_value = f"{session_root}/03"
    repo.load_meta.return_value = {"agent_name": "pathfinder", "turn_id": "03"}
    repo.to_root_relative.return_value = "test.xml"

    fs.path_exists.side_effect = lambda p: p == ".teddy/prompts"
    fs.list_directory.side_effect = lambda d: {
        ".teddy/prompts": ["pathfinder.xml", "developer.xml"],
        session_root: ["pathfinder.xml"],
    }.get(d, [])
    fs.read_file.return_value = "<prompt/>"
    prompts.fetch_system_prompt.return_value = "Agent Name: X\n\n<prompt/>"

    service.set_session_agent("test-casing", raw_agent)

    persisted = repo.save_meta.call_args.args[1]
    assert persisted["agent_name"] == expected_agent, (
        "meta.yaml must persist the canonical agent name, got "
        f"{persisted['agent_name']!r}"
    )
