import yaml
from teddy_executor.core.ports.outbound.config_service import IConfigService


def test_get_setting_block_reflects_flat_overrides(fs, container):
    """
    REQ: Flat overrides at the root (e.g., 'model') must propagate into
    nested blocks (e.g., 'llm.model') so that block lookups ('llm') are consistent.
    """
    # Arrange
    config_path = ".teddy/config.yaml"
    # User provides a flat 'model' override
    user_config = {"model": "user-overridden-model"}
    fs.create_dir(".teddy")
    fs.create_file(config_path, contents=yaml.dump(user_config))

    adapter = container.resolve(IConfigService)

    # Act
    llm_block = adapter.get_setting("llm")

    # Assert
    # This currently fails because 'llm' block is returned from the merged dict
    # BEFORE the dynamic shim in get_setting() is applied.
    assert llm_block is not None, "LLM block should exist (even if just from baseline)"
    assert llm_block.get("model") == "user-overridden-model", (
        f"Block lookup 'llm' should reflect flat 'model' override. Got: {llm_block.get('model')}"
    )


def test_merge_dicts_prunes_null_values(fs, container):
    """
    REQ: If a user sets a key to null (None) in their config, it should
    be removed from the merged configuration, effectively 'unsetting' a baseline default.
    """
    # Arrange
    config_path = ".teddy/config.yaml"
    # We want to 'unset' custom_llm_provider from the baseline
    user_config = {"llm": {"custom_llm_provider": None}}
    fs.create_dir(".teddy")
    fs.create_file(config_path, contents=yaml.dump(user_config))

    adapter = container.resolve(IConfigService)

    # Act
    llm_block = adapter.get_setting("llm")

    # Assert
    # This currently fails because _merge_dicts just sets base[key] = None,
    # keeping the key in the dictionary.
    assert "custom_llm_provider" not in llm_block, (
        "Setting a key to null should remove it from the merged config"
    )
