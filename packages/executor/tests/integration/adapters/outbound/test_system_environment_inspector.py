def test_get_environment_info():
    """
    Tests that the SystemEnvironmentInspector returns a dictionary with
    the expected keys and non-empty string values.
    """
    from teddy_executor.adapters.outbound.system_environment_inspector import (
        SystemEnvironmentInspector,
    )

    # Arrange
    adapter = SystemEnvironmentInspector()
    expected_keys = {
        "os_name",
        "os_version",
        "python_version",
        "cwd",
        "shell",
    }

    # Act
    env_info = adapter.get_environment_info()

    # Assert
    assert isinstance(env_info, dict)
    assert set(env_info.keys()) == expected_keys
    for key, value in env_info.items():
        assert isinstance(value, str), f"Value for '{key}' is not a string."
        assert value, f"Value for '{key}' is empty."
