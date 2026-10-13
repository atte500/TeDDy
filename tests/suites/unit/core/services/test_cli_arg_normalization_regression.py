"""
Regression tests for CLI arg normalization:

1. Agent name case-insensitivity: SessionService.create_session should
   resolve prompt files case-insensitively.
2. Context path normalization: _prepare_session_context should strip
   leading slashes, ./ prefixes, and normalize backslashes.
"""

from datetime import datetime, timezone

import pytest

from teddy_executor.core.domain.models.session import SessionOptions
from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.outbound import IConfigService, IFileSystemManager
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.ports.outbound.session_repository import ISessionRepository
from teddy_executor.core.ports.outbound.time_service import ITimeService
from teddy_executor.core.services.session_service import SessionService
from tests.harness.setup.mocking import register_mock


@pytest.fixture
def mock_deps(container):
    """Minimal, auto-specced dependencies for SessionService.

    Uses the harness ``register_mock`` helper so each collaborator port is
    bound to its contract (``POSIXPathMock(spec=...)``), preventing signature
    drift while keeping the unit under test free of real infrastructure.
    """
    fs = register_mock(container, IFileSystemManager)
    repo = register_mock(container, ISessionRepository)
    time_ = register_mock(container, ITimeService)
    pm = register_mock(container, IPromptManager)
    init = register_mock(container, IInitUseCase)
    config = register_mock(container, IConfigService)

    time_.now.return_value = datetime(2026, 8, 21, 10, 0, 0, tzinfo=timezone.utc)
    time_.now_utc.return_value = datetime(2026, 8, 21, 10, 0, 0, tzinfo=timezone.utc)
    pm.get_available_agents.return_value = ["developer", "pathfinder", "debugger"]
    init.ensure_initialized.return_value = None
    config.get_setting.return_value = True

    return {
        "file_system_manager": fs,
        "repository": repo,
        "time_service": time_,
        "prompt_manager": pm,
        "init_service": init,
        "config_service": config,
    }


class TestAgentNameCaseInsensitivity:
    """These tests verify that agent names are matched case-insensitively."""

    def test_create_session_with_capitalized_agent_name(self, mock_deps):
        """
        When agent_name is "Developer" but prompt file is "developer.xml",
        create_session should succeed (case-insensitive).
        """
        fs = mock_deps["file_system_manager"]

        # Simulate .teddy/prompts/ directory with developer.xml
        # Must also handle init.context path check in _prepare_session_context
        def _path_exists(p):
            return p in (".teddy/prompts", ".teddy/init.context")

        fs.path_exists.side_effect = _path_exists
        fs.list_directory.return_value = ["developer.xml"]
        fs.read_file.return_value = "<prompt>developer content</prompt>"

        service = SessionService(**mock_deps)
        options = SessionOptions(name="test", agent_name="Developer")

        session_root = service.create_session(options)
        assert session_root is not None
        # Should not raise ValueError
        # Verify prompt was found (no error raised)
        # Check that prompt file was copied to session root
        call_args = [c[0] for c in fs.write_file.call_args_list]
        assert any("developer.xml" in str(a[0]) for a in call_args)

    def test_create_session_with_lowercase_agent_name(self, mock_deps):
        """
        Lowercase agent name still works.
        """
        fs = mock_deps["file_system_manager"]

        def _path_exists(p):
            return p in (".teddy/prompts", ".teddy/init.context")

        fs.path_exists.side_effect = _path_exists
        fs.list_directory.return_value = ["developer.xml"]
        fs.read_file.return_value = "<prompt>developer content</prompt>"

        service = SessionService(**mock_deps)
        options = SessionOptions(name="test", agent_name="developer")

        session_root = service.create_session(options)
        assert session_root is not None

    def test_create_session_with_uppercase_prompt_file(self, mock_deps):
        """
        If prompt file is "DEVELOPER.XML" and agent is "developer",
        should still match case-insensitively.
        """
        fs = mock_deps["file_system_manager"]

        def _path_exists(p):
            return p in (".teddy/prompts", ".teddy/init.context")

        fs.path_exists.side_effect = _path_exists
        fs.list_directory.return_value = ["DEVELOPER.XML"]
        fs.read_file.return_value = "<prompt>content</prompt>"

        service = SessionService(**mock_deps)
        options = SessionOptions(name="test", agent_name="developer")

        session_root = service.create_session(options)
        assert session_root is not None

    def test_create_session_with_mixed_case_agent_name(self, mock_deps):
        """
        Agent name "DeVeLoPeR" should match "developer.xml".
        """
        fs = mock_deps["file_system_manager"]

        def _path_exists(p):
            return p in (".teddy/prompts", ".teddy/init.context")

        fs.path_exists.side_effect = _path_exists
        fs.list_directory.return_value = ["developer.xml"]
        fs.read_file.return_value = "<prompt>content</prompt>"

        service = SessionService(**mock_deps)
        options = SessionOptions(name="test", agent_name="DeVeLoPeR")

        session_root = service.create_session(options)
        assert session_root is not None


class TestContextPathNormalization:
    """These tests verify that context paths are normalized."""

    @pytest.fixture
    def service(self, mock_deps):
        """Service with init.context ready."""
        fs = mock_deps["file_system_manager"]
        fs.path_exists.side_effect = lambda p: p == ".teddy/init.context"
        fs.read_file.return_value = "# init\nsome/path.md\n"
        return SessionService(**mock_deps)

    def test_leading_slash_is_stripped(self, service):
        """
        Path "/abs/path/file.md" should become "abs/path/file.md".
        """
        options = SessionOptions(
            name="test",
            agent_name="developer",
            additional_context=["/abs/path/file.md"],
        )
        result = service._prepare_session_context(".teddy/sessions/test", options)
        assert "abs/path/file.md" in result
        assert "/abs/path/file.md" not in result

    def test_dot_slash_prefix_is_stripped(self, service):
        """
        Path "./docs/readme.md" should become "docs/readme.md".
        """
        options = SessionOptions(
            name="test", agent_name="developer", additional_context=["./docs/readme.md"]
        )
        result = service._prepare_session_context(".teddy/sessions/test", options)
        assert "docs/readme.md" in result
        assert "./docs/readme.md" not in result

    def test_backslashes_normalized(self, service):
        """
        Path "docs\\guide.md" should become "docs/guide.md".
        """
        options = SessionOptions(
            name="test", agent_name="developer", additional_context=["docs\\guide.md"]
        )
        result = service._prepare_session_context(".teddy/sessions/test", options)
        assert "docs/guide.md" in result
        assert "docs\\guide.md" not in result

    def test_all_three_forms_normalized(self, service):
        """Multiple paths with different issues all normalized."""
        options = SessionOptions(
            name="test",
            agent_name="developer",
            additional_context=[
                "/abs/path/file.md",
                "./docs/readme.md",
                "docs\\guide.md",
            ],
        )
        result = service._prepare_session_context(".teddy/sessions/test", options)
        lines = result.strip().split("\n")
        assert "abs/path/file.md" in lines
        assert "docs/readme.md" in lines
        assert "docs/guide.md" in lines
        # All original problematic forms should be gone
        assert "/abs/path/file.md" not in lines
        assert "./docs/readme.md" not in lines
        assert "docs\\guide.md" not in lines

    def test_empty_context_entry_skipped(self, service):
        """Empty string from -c should not add any line."""
        options = SessionOptions(
            name="test",
            agent_name="developer",
            additional_context=["/valid/path.md", ""],
        )
        result = service._prepare_session_context(".teddy/sessions/test", options)
        lines = [line for line in result.strip().split("\n") if line]
        # Should not contain an empty line
        assert "" not in lines

    def test_dot_hidden_preserved(self, service):
        """Paths like .hidden/file.md should retain leading dot."""
        options = SessionOptions(
            name="test", agent_name="developer", additional_context=[".hidden/file.md"]
        )
        result = service._prepare_session_context(".teddy/sessions/test", options)
        assert ".hidden/file.md" in result

    @pytest.mark.parametrize(
        "raw_entry",
        [
            "[docs/readme.md](docs/readme.md)",
            "[docs/readme.md](docs\\readme.md)",
        ],
    )
    def test_markdown_link_entry_extracts_target(self, service, raw_entry):
        """Scenario: a `-c` Markdown-link entry seeds the link TARGET.

        A `[label](target)` entry (forward- or back-slash target) must be
        reduced to the normalized target path, never seeded verbatim. Whole-line
        assertions are required because the target is a SUBSTRING of the raw
        link, which would make a plain membership check pass spuriously.
        """
        options = SessionOptions(
            name="test",
            agent_name="developer",
            additional_context=[raw_entry],
        )

        result = service._prepare_session_context(".teddy/sessions/test", options)

        lines = result.strip().split("\n")
        assert "docs/readme.md" in lines
        assert raw_entry not in lines
