from tests.harness.setup.test_environment import TestEnvironment
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


def test_environment_isolates_container(monkeypatch, container):
    """
    Verifies that TestEnvironment provides a fresh container and patches the global one.
    """
    env = TestEnvironment(monkeypatch)
    env.setup()

    # Check that we can get a service
    fs = env.get_service(IFileSystemManager)
    assert fs is not None

    # Check that the global container in container.py is patched
    import teddy_executor.container as container_mod

    assert container_mod._container is env.container

    env.teardown()


def test_environment_workspace_management(monkeypatch, tmp_path, container):
    """Verifies that the environment can anchor services to a specific workspace."""
    env = TestEnvironment(monkeypatch, workspace=tmp_path)
    env.setup()

    # If the environment is anchored to tmp_path, the FileSystemAdapter
    # (or its mock if we use one) should be configured accordingly.
    assert env.workspace == tmp_path

    env.teardown()


def test_environment_automated_workspace_lifecycle(monkeypatch, container):
    """
    Scenario 4: TestEnvironment should create and cleanup its own workspace
    under tests/.tmp/ if none is provided.
    """
    env = TestEnvironment(monkeypatch)
    env.setup()

    workspace = env.workspace
    assert workspace is not None
    # Use as_posix() to ensure cross-platform string matching
    assert "tests/.tmp" in workspace.as_posix()
    assert workspace.exists()
    assert workspace.is_dir()

    # Create a dummy file in the workspace
    (workspace / "dummy.txt").write_text("hello", encoding="utf-8")

    # Teardown should delete the workspace
    env.teardown()
    assert not workspace.exists()


def test_filesystem_mock_normalizes_paths_systemically(env):
    """
    REGRESSION: Verifies that the filesystem mock normalizes paths to POSIX
    format regardless of the host OS or call convention.
    """
    mock_fs = env.get_mock_filesystem()

    # Simulate a call from production code using Windows-style paths
    mock_fs.read_file("some\\windows\\path.txt")

    # This should pass even on non-Windows systems once the fix is applied,
    # as the mock will normalize the call to POSIX.
    mock_fs.read_file.assert_called_with("some/windows/path.txt")


def test_test_environment_mock_port_registers_and_returns_posix_path_mock(monkeypatch):
    """
    Harness: mock_port MUST create, register, and return a POSIXPathMock.
    """
    from teddy_executor.core.ports.outbound import IShellExecutor
    from tests.harness.setup.test_environment import TestEnvironment
    from tests.harness.setup.mocking import POSIXPathMock

    env = TestEnvironment(monkeypatch).setup()

    # 1. Action: Mock a port
    mock = env.mock_port(IShellExecutor)

    # 2. Assert: It is a POSIXPathMock with correct spec
    assert isinstance(mock, POSIXPathMock)

    # 3. Assert: It is registered in the container
    resolved = env.get_service(IShellExecutor)
    assert resolved == mock
