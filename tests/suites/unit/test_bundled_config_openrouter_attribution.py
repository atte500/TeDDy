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
    assert headers["X-OpenRouter-Categories"].split(",") == ["cli-agent"]


def test_bundled_config_keeps_the_app_publicly_listed():
    headers = _bundled_llm_settings()["extra_headers"]

    assert "X-OpenRouter-App-Visibility" not in headers


def test_user_null_override_suppresses_bundled_headers(tmp_path):
    """A user config setting ``llm.extra_headers: null`` opts out of attribution."""
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir()
    (teddy_dir / "config.yaml").write_text(
        "llm:\n  extra_headers: null\n", encoding="utf-8"
    )

    adapter = YamlConfigAdapter(
        config_path=".teddy/config.yaml", root_dir=str(tmp_path)
    )

    assert "extra_headers" not in adapter.get_setting("llm")
