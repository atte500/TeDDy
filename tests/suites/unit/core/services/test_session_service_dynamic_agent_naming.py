import punq
from tests.harness.setup.mocking import register_mock
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.session_repository import ISessionRepository
from teddy_executor.core.ports.outbound.time_service import ITimeService
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.domain.models.session import SessionOptions
from teddy_executor.core.services.session_service import SessionService


class TestCreateSessionDynamicAgentNaming:
    """
    Contract test: ensure SessionService.create_session writes the agent prompt
    to the session root using the agent name (e.g., architect.xml),
    never inside a turn directory.
    """

    def test_creates_prompt_at_session_root_with_agent_name(self):
        # Arrange
        container = punq.Container()
        fs_mock = register_mock(container, IFileSystemManager)
        fs_mock.path_exists.return_value = True
        fs_mock.read_file.return_value = "<prompt/>\n"

        svc = SessionService(
            file_system_manager=fs_mock,
            repository=register_mock(container, ISessionRepository),
            time_service=register_mock(container, ITimeService),
            prompt_manager=register_mock(container, IPromptManager),
            init_service=register_mock(container, IInitUseCase),
        )

        options = SessionOptions(
            name="test-dynamic",
            agent_name="architect",
            initial_request="test request",
        )

        # Act
        session_root = svc.create_session(options)

        # Assert: find all write_file calls for .xml files
        xml_writes = [
            call
            for call in fs_mock.write_file.call_args_list
            if call[0][0].endswith(".xml")
        ]

        assert len(xml_writes) >= 1, "Expected at least one .xml write"

        prompt_path = xml_writes[0][0][0]
        # Must be in session root, NOT inside a turn directory
        assert "/01/" not in prompt_path, (
            f"Prompt must not be written to turn directory: {prompt_path}"
        )
        # Must contain the agent name
        assert "architect" in prompt_path, (
            f"Prompt path must include agent name: {prompt_path}"
        )
        # Must end with agent name .xml
        assert prompt_path.endswith("architect.xml"), (
            f"Prompt path must end with agent_name.xml: {prompt_path}"
        )
        # Must be under session root (no turn segment)
        assert prompt_path.startswith(session_root), (
            f"Prompt path must start with session root: {session_root} vs {prompt_path}"
        )
