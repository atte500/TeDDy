from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)


def test_list_directory_recursive_finds_nested_files(fs, mock_edit_simulator):
    # Arrange
    # fs is the pyfakefs fixture
    fs.create_file("/app/src/main.py", contents="print('hello')")
    fs.create_file("/app/src/utils/helpers.py", contents="def help(): pass")
    fs.create_file("/app/docs/readme.md", contents="# Readme")

    adapter = LocalFileSystemAdapter(
        edit_simulator=mock_edit_simulator, root_dir="/app"
    )

    # Act
    files = adapter.list_directory_recursive("src")

    # Assert
    # Paths should be relative to the root_dir (standard for this adapter's output)
    # or at least consistent. LocalFileSystemAdapter usually returns relative paths
    # as strings if it's following the port contract "list_directory_recursive(self, path: str) -> list[str]"
    expected = ["src/main.py", "src/utils/helpers.py"]
    assert sorted(files) == sorted(expected)


def test_list_directory_recursive_respects_ignores(fs, mock_edit_simulator):
    # Arrange
    fs.create_file("/app/.gitignore", contents="*.log\nnode_modules/")
    fs.create_file("/app/src/main.py", contents="print('hello')")
    fs.create_file("/app/src/app.log", contents="some log")
    fs.create_file("/app/node_modules/dep/index.js", contents="...")
    fs.create_file("/app/.teddyignore", contents="secret.txt")
    fs.create_file("/app/secret.txt", contents="shhh")

    adapter = LocalFileSystemAdapter(
        edit_simulator=mock_edit_simulator, root_dir="/app"
    )

    # Act
    files = adapter.list_directory_recursive(".")

    # Assert
    # .gitignore, .teddyignore, and ignored files/dirs should be excluded
    # Note: Whether .gitignore itself is included depends on system-wide 'respecting ignores' definition
    # But files matching the patterns MUST be excluded.
    # Also .git is usually implicitly ignored by pathspec if using 'gitwildmatch' or similar logic.
    assert "src/app.log" not in files
    assert "node_modules/dep/index.js" not in files
    assert "secret.txt" not in files
    assert "src/main.py" in files
