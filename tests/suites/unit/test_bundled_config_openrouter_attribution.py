"""Guards the bundled OpenRouter app-attribution headers.

The shipped ``config.yaml`` must attribute usage to TeDDy so OpenRouter's
leaderboard credits this project instead of LiteLLM's default app.
"""

from importlib.resources import files

from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter

_SITE_URL = "https://github.com/atte500/teddy"


def _bundled_llm_settings() -> dict:
    resource = files("teddy_executor.resources.config").joinpath("config.yaml")
    adapter = YamlConfigAdapter(
        config_path="config.yaml", root_dir=str(resource.parent)
    )
    return adapter.get_setting("llm")


def test_bundled_config_attributes_requests_to_teddy():
    headers = _bundled_llm_settings()["extra_headers"]

    assert headers["HTTP-Referer"] == _SITE_URL
    assert headers["X-Title"] == "TeDDy"
    assert headers["X-OpenRouter-Title"] == "TeDDy"
    assert "cli-agent" in headers["X-OpenRouter-Categories"].split(",")


def test_bundled_config_keeps_the_app_publicly_listed():
    headers = _bundled_llm_settings()["extra_headers"]

    assert "X-OpenRouter-App-Visibility" not in headers
