from tests.harness.setup.test_environment import TestEnvironment
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


def test_environment_isolates_container(monkeypatch):
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


def test_environment_workspace_management(monkeypatch, tmp_path):
    """Verifies that the environment can anchor services to a specific workspace."""
    env = TestEnvironment(monkeypatch, workspace=tmp_path)
    env.setup()

    # If the environment is anchored to tmp_path, the FileSystemAdapter
    # (or its mock if we use one) should be configured accordingly.
    assert env.workspace == tmp_path

    env.teardown()
