"""Unit tests for the ``YamlConfigAdapter.set_env_variable`` persistence contract.

Contract: persist a secret to the ``.env`` file inside the config directory
WITHOUT mutating ``os.environ``. Non-mutation is what keeps the key out of the
``EXECUTE`` child shells that TeDDy spawns inside the user's repo.
"""

import os

from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter


def test_set_env_variable_persists_key_without_mutating_os_environ(
    tmp_path, monkeypatch
):
    """The key lands in ``.teddy/.env`` and ``os.environ`` is left untouched."""
    # Arrange
    monkeypatch.delenv("TEDDY_LLM_API_KEY", raising=False)
    adapter = YamlConfigAdapter(
        config_path=".teddy/config.yaml", root_dir=str(tmp_path)
    )
    env_path = tmp_path / ".teddy" / ".env"
    assert not env_path.exists()

    # Act
    adapter.set_env_variable("TEDDY_LLM_API_KEY", "sk-test-key")

    # Assert - the key is persisted to the env file ...
    assert env_path.exists()
    content = env_path.read_text(encoding="utf-8")
    assert "TEDDY_LLM_API_KEY" in content
    assert "sk-test-key" in content
    # ... and the process environment is left untouched.
    assert "TEDDY_LLM_API_KEY" not in os.environ
