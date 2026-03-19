from tests.harness.setup.test_environment import TestEnvironment
from teddy_executor.core.ports.outbound.environment_inspector import (
    IEnvironmentInspector,
)


def test_get_environment_info(monkeypatch):
    """
    Tests that the SystemEnvironmentInspector returns a dictionary with
    the expected keys and non-empty string values.
    """
    env = TestEnvironment(monkeypatch).setup().with_real_inspector()
    inspector = env.get_service(IEnvironmentInspector)

    expected_keys = {
        "os_name",
        "os_version",
        "python_version",
        "cwd",
        "shell",
    }

    # Act
    env_info = inspector.get_environment_info()

    # Assert
    assert isinstance(env_info, dict)
    assert set(env_info.keys()) == expected_keys
    for key, value in env_info.items():
        assert isinstance(value, str), f"Value for '{key}' is not a string."
        assert value, f"Value for '{key}' is empty."
