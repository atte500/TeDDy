from pathlib import Path
import punq
from tests.harness.setup.mocking import register_mock
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.session_repository import ISessionRepository
from teddy_executor.core.ports.outbound.time_service import ITimeService
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.services.session_service import SessionService


class TestCloneSessionArtifactsContract:
    """
    Contract test ensuring _clone_session_artifacts strictly adheres to
    the session-root prompt placement rule and never copies prompts to turn directories.
    """

    def test_clone_artifacts_targets_session_root_not_turn(self):
        # Arrange
        container = punq.Container()
        fs_mock = register_mock(container, IFileSystemManager)
        fs_mock.path_exists.return_value = True
        fs_mock.read_file.return_value = "<prompt/>Session Root"

        svc = SessionService(
            file_system_manager=fs_mock,
            repository=register_mock(container, ISessionRepository),
            time_service=register_mock(container, ITimeService),
            prompt_manager=register_mock(container, IPromptManager),
            init_service=register_mock(container, IInitUseCase),
        )

        src_session = Path(".teddy/sessions/test-session")
        dest_session = Path(".teddy/sessions/test-session-backup")
        src_turn = src_session / "01"
        dest_turn = dest_session / "01"
        meta = {"agent_name": "architect"}

        # Act
        svc._clone_session_artifacts(
            src_session=src_session,
            dest_session=dest_session,
            src_turn=src_turn,
            dest_turn=dest_turn,
            meta=meta,
        )

        # Assert: Verify prompt XML was written exactly once and strictly to session root
        xml_calls = [
            call
            for call in fs_mock.write_file.call_args_list
            if call[0][0].endswith(".xml")
        ]
        assert len(xml_calls) == 1, "Prompt should be written exactly once."

        target_path = xml_calls[0][0][0]
        # Ensure it does NOT contain turn directory patterns
        assert (
            "/01/" not in target_path
            and "/02/" not in target_path
            and "/99/" not in target_path
        ), f"Prompt MUST NOT be copied to a turn directory. Found: {target_path}"

        # Ensure it targets the session root
        assert target_path.endswith("architect.xml"), (
            "Prompt target must retain .xml extension."
        )
