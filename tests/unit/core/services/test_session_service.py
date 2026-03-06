from unittest.mock import MagicMock, patch

import pytest

from teddy_executor.core.services.session_service import SessionService


@pytest.fixture
def mock_fs():
    return MagicMock()


@pytest.fixture
def service(mock_fs):
    # We will need a way to fetch prompts, maybe another mock or just dependency on fs
    return SessionService(file_system_manager=mock_fs)


def test_create_session_orchestrates_filesystem_correctly(service, mock_fs):
    """
    Tests that create_session creates the correct directory structure and files.
    """
    # Arrange
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
        mock_fs.create_directory.assert_any_call(".teddy/sessions/feat-x/01")

        # 2. session.context creation (with comments stripped)
        mock_fs.write_file.assert_any_call(
            ".teddy/sessions/feat-x/session.context", clean_context
        )

        # 3. system_prompt.xml creation
        mock_fs.write_file.assert_any_call(
            ".teddy/sessions/feat-x/01/system_prompt.xml", agent_prompt
        )

        # 4. meta.yaml creation (just check it was called, parsing checked in acceptance)
        # We use ANY for the content since it has a dynamic timestamp
        from unittest.mock import ANY

        mock_fs.write_file.assert_any_call(".teddy/sessions/feat-x/01/meta.yaml", ANY)
