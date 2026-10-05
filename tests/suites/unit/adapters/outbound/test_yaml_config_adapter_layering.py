from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter


def test_config_loads_baseline_when_user_config_missing(tmp_path):
    # Given: No user config at .teddy/config.yaml
    # When: We instantiate the adapter
    adapter = YamlConfigAdapter(
        config_path=".teddy/config.yaml", root_dir=str(tmp_path)
    )

    # Then: It should return values from the bundled baseline
    # Note: 'execution.max_output_lines' is a known key in our baseline
    val = adapter.get_setting("execution.max_output_lines")
    assert val is not None
    assert isinstance(val, int)


def test_baseline_llm_timeout_default(tmp_path):
    """Baseline config should provide timeout=300 under the llm section."""
    # Given: No user config at .teddy/config.yaml
    adapter = YamlConfigAdapter(
        config_path=".teddy/config.yaml", root_dir=str(tmp_path)
    )

    # When: We retrieve llm.timeout
    timeout = adapter.get_setting("llm.timeout")

    # Then: It should equal 300 (the default for LLM completion calls)
    assert timeout == 300, f"Expected 300 but got {timeout}"


def test_user_config_overrides_baseline(tmp_path):
    # Given: A user config that overrides a baseline value
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir()
    user_config = teddy_dir / "config.yaml"
    user_config.write_text("execution:\n  max_output_lines: 999", encoding="utf-8")

    # When: We instantiate the adapter
    adapter = YamlConfigAdapter(
        config_path=".teddy/config.yaml", root_dir=str(tmp_path)
    )

    # Then: The user value should take precedence
    assert adapter.get_setting("execution.max_output_lines") == 999


def test_baseline_llm_api_key_is_an_env_var_reference(tmp_path, monkeypatch):
    """The bundled baseline ships ``llm.api_key`` as an env-var reference.

    Migration guard: the shipped default must resolve the key from
    ``.teddy/.env`` / the shell instead of shipping a literal empty value that
    would make the missing-key path look satisfied.
    """
    # Given: the env var is available to the process
    monkeypatch.setenv("TEDDY_LLM_API_KEY", "resolved-from-env")

    # When: the adapter loads the bundled baseline
    adapter = YamlConfigAdapter(
        config_path=".teddy/config.yaml", root_dir=str(tmp_path)
    )

    # Then: llm.api_key resolves through interpolation
    assert adapter.get_setting("llm.api_key") == "resolved-from-env"
