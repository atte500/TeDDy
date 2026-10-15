"""Unit: SessionService._resolve_agent_prompt prefers the Markdown prompt file.

When a stem has both a ``.xml`` and a ``.md`` file in ``.teddy/prompts/``, the
resolver must return the ``.md`` file (and its content) regardless of directory
listing order, so a pre-authored Markdown prompt always wins over a stale XML
one. This is the third resolver site migrated alongside
``PromptManager._find_prompt_file`` and ``prompts._search_prompt_in_dir``.
"""

from tests.harness.setup.mocking import register_mock
from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.ports.outbound.session_repository import ISessionRepository
from teddy_executor.core.ports.outbound.time_service import ITimeService
from teddy_executor.core.services.session_service import SessionService


def _make_service(container):
    """Builds a SessionService with fully mocked ports (no real filesystem)."""
    fs = register_mock(container, IFileSystemManager)
    repo = register_mock(container, ISessionRepository)
    time_service = register_mock(container, ITimeService)
    prompts = register_mock(container, IPromptManager)
    init = register_mock(container, IInitUseCase)
    config = register_mock(container, IConfigService)

    service = SessionService(
        file_system_manager=fs,
        repository=repo,
        time_service=time_service,
        prompt_manager=prompts,
        init_service=init,
        config_service=config,
    )
    return service, fs


def test_resolve_agent_prompt_prefers_md_over_xml(container):
    """When a stem has both a ``.xml`` and a ``.md`` file, ``.md`` wins.

    The ``.xml`` is listed FIRST so a naive first-stem-match would return it;
    the resolver must actively prefer the Markdown file.
    """
    service, fs = _make_service(container)

    fs.path_exists.side_effect = lambda p: p == ".teddy/prompts"
    fs.list_directory.side_effect = lambda d: {
        ".teddy/prompts": ["pathfinder.xml", "pathfinder.md"],
    }.get(d, [])
    fs.read_file.side_effect = lambda p: {
        ".teddy/prompts/pathfinder.md": "# Pathfinder (Markdown)",
    }.get(p, "")

    # Act
    prompt_filename, prompt_content = service._resolve_agent_prompt("pathfinder")

    # Assert
    assert prompt_filename == "pathfinder.md"
    assert prompt_content == "# Pathfinder (Markdown)"
