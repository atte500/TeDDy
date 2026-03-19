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

    # Check that the global container in __main__ is patched
    import teddy_executor.__main__ as main

    assert main.container is env.container

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
