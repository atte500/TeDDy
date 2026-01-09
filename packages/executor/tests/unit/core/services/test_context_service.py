from unittest.mock import MagicMock


def test_get_context_creates_teddy_dir_on_first_run():
    """
    Tests that get_context creates the .teddy directory and default files
    if they do not exist.
    """
    # Arrange
    mock_fsm = MagicMock()
    mock_rtg = MagicMock()
    mock_ei = MagicMock()

    from teddy_executor.core.services.context_service import ContextService

    service = ContextService(
        file_system_manager=mock_fsm,
        repo_tree_generator=mock_rtg,
        environment_inspector=mock_ei,
    )

    # Simulate .teddy directory not existing
    mock_fsm.path_exists.return_value = False

    # Mock return values for the rest of the function to avoid errors
    mock_fsm.read_file.return_value = ""
    mock_rtg.generate_tree.return_value = "<tree>"
    mock_ei.get_environment_info.return_value = {}

    # Act
    service.get_context()

    # Assert
    # Check that the directory setup happens
    mock_fsm.path_exists.assert_called_once_with(".teddy")
    mock_fsm.create_directory.assert_called_once_with(".teddy")
    mock_fsm.write_file.assert_any_call(".teddy/.gitignore", "*")

    expected_temp_context = "# This file is managed by the AI. It determines the file context for the NEXT turn."
    mock_fsm.write_file.assert_any_call(".teddy/temp.context", expected_temp_context)

    # Check that repo tree is generated and saved
    mock_rtg.generate_tree.assert_called_once()
    mock_fsm.write_file.assert_any_call(".teddy/repotree.txt", "<tree>")

    # Check the new default permanent context
    expected_permanent_context = (
        "# This file is managed by the User. It provides persistent file context.\n"
        ".teddy/repotree.txt\n"
        ".teddy/temp.context\n"
        ".teddy/perm.context\n"
        "README.md\n"
        "docs/ARCHITECTURE.md\n"
    )
    mock_fsm.write_file.assert_any_call(
        ".teddy/perm.context", expected_permanent_context
    )


def test_get_context_reads_and_processes_context_files():
    """
    Tests that get_context reads file paths from context.txt and
    permanent_context.txt, fetches their content, and handles missing files.
    """
    # Arrange
    mock_fsm = MagicMock()
    mock_rtg = MagicMock()
    mock_ei = MagicMock()

    from teddy_executor.core.services.context_service import ContextService

    service = ContextService(
        file_system_manager=mock_fsm,
        repo_tree_generator=mock_rtg,
        environment_inspector=mock_ei,
    )

    # Don't create .teddy dir in this test
    mock_fsm.path_exists.return_value = True

    # Mock reading the context list files
    comment_line_1 = "# This is a comment"
    comment_line_2 = "# And another one"
    context_txt_content = f"src/main.py\n{comment_line_1}\nREADME.md"
    permanent_context_content = f"pyproject.toml\nnon_existent.py\n{comment_line_2}"

    # Mock reading the content of the actual files
    def read_file_side_effect(path):
        if path == ".teddy/temp.context":
            return context_txt_content
        if path == ".teddy/perm.context":
            return permanent_context_content
        if path == "src/main.py":
            return "print('hello')"
        if path == "README.md":
            return "# My Project"
        if path == "pyproject.toml":
            return "[tool.poetry]"
        if path == "non_existent.py":
            raise FileNotFoundError
        return ""  # Default for .gitignore

    mock_fsm.read_file.side_effect = read_file_side_effect

    # Mock other dependencies
    mock_rtg.generate_tree.return_value = "tree"
    mock_ei.get_environment_info.return_value = {"os": "test"}

    # Act
    result = service.get_context()

    # Assert
    assert len(result.file_contexts) == 4

    found_main = next(
        fc for fc in result.file_contexts if fc.file_path == "src/main.py"
    )
    assert found_main.status == "found"
    assert found_main.content == "print('hello')"

    found_readme = next(
        fc for fc in result.file_contexts if fc.file_path == "README.md"
    )
    assert found_readme.status == "found"

    found_toml = next(
        fc for fc in result.file_contexts if fc.file_path == "pyproject.toml"
    )
    assert found_toml.status == "found"

    not_found_py = next(
        fc for fc in result.file_contexts if fc.file_path == "non_existent.py"
    )
    assert not_found_py.status == "not_found"

    # Assert that the service did NOT try to read the comment lines as files
    read_calls = [call[0][0] for call in mock_fsm.read_file.call_args_list]
    assert comment_line_1 not in read_calls
    assert comment_line_2 not in read_calls


def test_context_service_instantiation():
    """
    Tests that the ContextService can be instantiated with its dependencies.
    """
    # Arrange
    mock_file_system_manager = MagicMock()
    mock_repo_tree_generator = MagicMock()
    mock_env_inspector = MagicMock()

    # Act
    from teddy_executor.core.services.context_service import ContextService

    service = ContextService(
        file_system_manager=mock_file_system_manager,
        repo_tree_generator=mock_repo_tree_generator,
        environment_inspector=mock_env_inspector,
    )

    # Assert
    assert service.file_system_manager == mock_file_system_manager
    assert service.repo_tree_generator == mock_repo_tree_generator
    assert service.environment_inspector == mock_env_inspector
