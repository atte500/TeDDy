from pathlib import Path
from unittest.mock import ANY, patch

from teddy_executor.core.ports.outbound.session_manager import ISessionManager


def test_create_session_orchestrates_filesystem_correctly(env):
    """
    Tests that create_session creates the correct directory structure and files.
    """
    # Arrange
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    session_name = "feat-x"
    agent_name = "pathfinder"
    # Include a comment to test stripping
    init_context = "README.md\n# comment\ndocs/project/PROJECT.md"
    clean_context = "README.md\ndocs/project/PROJECT.md"
    agent_prompt = "<prompt>Pathfinder content</prompt>"

    mock_fs.read_file.return_value = init_context

    # Mock find_prompt_content to avoid dependency on filesystem during unit test
    with patch(
        "teddy_executor.core.services.session_service.find_prompt_content"
    ) as mock_find_prompt:
        mock_find_prompt.return_value = agent_prompt

        # Act
        service.create_session(name=session_name, agent_name=agent_name)

        # Assert
        # 1. Directory creation
        mock_fs.create_directory.assert_any_call(str(Path(".teddy/sessions/feat-x/01")))

        # 2. session.context creation (with comments stripped)
        mock_fs.write_file.assert_any_call(
            str(Path(".teddy/sessions/feat-x/session.context")), clean_context
        )

        # 3. pathfinder.xml creation
        mock_fs.write_file.assert_any_call(
            str(Path(".teddy/sessions/feat-x/01/pathfinder.xml")), agent_prompt
        )

        # 4. meta.yaml creation
        mock_fs.write_file.assert_any_call(
            str(Path(".teddy/sessions/feat-x/01/meta.yaml")), ANY
        )
