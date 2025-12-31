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

    from teddy.core.services.context_service import ContextService

    service = ContextService(
        file_system_manager=mock_fsm,
        repo_tree_generator=mock_rtg,
        environment_inspector=mock_ei,
    )

    # Simulate .teddy directory not existing
    mock_fsm.path_exists.return_value = False

    # Mock return values for the rest of the function to avoid errors
    mock_fsm.read_file.return_value = ""
    mock_rtg.generate_tree.return_value = ""
    mock_ei.get_environment_info.return_value = {}

    # Act
    service.get_context()

    # Assert
    mock_fsm.path_exists.assert_called_once_with(".teddy")
    mock_fsm.create_directory.assert_called_once_with(".teddy")
    mock_fsm.write_file.assert_any_call(".teddy/.gitignore", "*")
    mock_fsm.write_file.assert_any_call(".teddy/context.json", "[]")

    expected_permanent_context = "README.md\n" "docs/ARCHITECTURE.md\n" "repotree.txt\n"
    mock_fsm.write_file.assert_any_call(
        ".teddy/permanent_context.txt", expected_permanent_context
    )


def test_get_context_reads_and_processes_context_files():
    """
    Tests that get_context reads file paths from context.json and
    permanent_context.txt, fetches their content, and handles missing files.
    """
    # Arrange
    import json

    mock_fsm = MagicMock()
    mock_rtg = MagicMock()
    mock_ei = MagicMock()

    from teddy.core.services.context_service import ContextService

    service = ContextService(
        file_system_manager=mock_fsm,
        repo_tree_generator=mock_rtg,
        environment_inspector=mock_ei,
    )

    # Don't create .teddy dir in this test
    mock_fsm.path_exists.return_value = True

    # Mock reading the context list files
    context_json_content = json.dumps(["src/main.py", "README.md"])
    permanent_context_content = "pyproject.toml\nnon_existent.py"

    # Mock reading the content of the actual files
    def read_file_side_effect(path):
        if path == ".teddy/context.json":
            return context_json_content
        if path == ".teddy/permanent_context.txt":
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
    assert found_readme.content == "# My Project"

    found_toml = next(
        fc for fc in result.file_contexts if fc.file_path == "pyproject.toml"
    )
    assert found_toml.status == "found"
    assert found_toml.content == "[tool.poetry]"

    not_found_py = next(
        fc for fc in result.file_contexts if fc.file_path == "non_existent.py"
    )
    assert not_found_py.status == "not_found"
    assert not_found_py.content is None


def test_context_service_instantiation():
    """
    Tests that the ContextService can be instantiated with its dependencies.
    """
    # Arrange
    mock_file_system_manager = MagicMock()
    mock_repo_tree_generator = MagicMock()
    mock_env_inspector = MagicMock()

    # Act
    from teddy.core.services.context_service import ContextService

    service = ContextService(
        file_system_manager=mock_file_system_manager,
        repo_tree_generator=mock_repo_tree_generator,
        environment_inspector=mock_env_inspector,
    )

    # Assert
    assert service.file_system_manager == mock_file_system_manager
    assert service.repo_tree_generator == mock_repo_tree_generator
    assert service.environment_inspector == mock_env_inspector
