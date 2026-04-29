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
