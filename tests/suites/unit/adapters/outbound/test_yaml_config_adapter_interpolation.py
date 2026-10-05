"""Unit tests for ``YamlConfigAdapter``'s ``${VAR}`` interpolation (Logic deliverable).

Design: ``get_setting`` lazily interpolates ``${VAR}`` / ``${VAR:-default}``
tokens against a merged environment that layers ``.teddy/.env`` UNDER
``os.environ`` (so the real shell env wins). ``.teddy/.env`` is read FRESH on
every interpolating call, which is what keeps a key written mid-run live across
the transient ``IConfigService`` instances without any explicit refresh call.
"""

from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter

# A deliberately-fake secret value. detect-secrets would otherwise flag this
# high-entropy token as a "Base64 High Entropy String"; the inline pragma is
# the sanctioned false-positive mitigation (mirrors tests/harness/setup/mocks.py).
_DOTENV_FAKE_KEY = "sk-from-dotenv"  # pragma: allowlist secret


def _write_config(tmp_path, content: str) -> None:
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir(parents=True, exist_ok=True)
    (teddy_dir / "config.yaml").write_text(content, encoding="utf-8")


def _write_env(tmp_path, content: str) -> None:
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir(parents=True, exist_ok=True)
    (teddy_dir / ".env").write_text(content, encoding="utf-8")


def _adapter(tmp_path) -> YamlConfigAdapter:
    return YamlConfigAdapter(config_path=".teddy/config.yaml", root_dir=str(tmp_path))


def test_interpolation_resolves_var_from_dotenv_file(tmp_path, monkeypatch):
    """A ${VAR} token resolves from .teddy/.env."""
    monkeypatch.delenv("TEDDY_LLM_API_KEY", raising=False)
    _write_config(tmp_path, 'llm:\n  api_key: "${TEDDY_LLM_API_KEY}"\n')
    _write_env(tmp_path, f"TEDDY_LLM_API_KEY={_DOTENV_FAKE_KEY}\n")

    assert _adapter(tmp_path).get_setting("llm.api_key") == _DOTENV_FAKE_KEY


def test_interpolation_shell_env_wins_over_dotenv_file(tmp_path, monkeypatch):
    """A real shell env var overrides the same name in .teddy/.env."""
    monkeypatch.setenv("TEDDY_LLM_API_KEY", "sk-from-shell")
    _write_config(tmp_path, 'llm:\n  api_key: "${TEDDY_LLM_API_KEY}"\n')
    _write_env(tmp_path, f"TEDDY_LLM_API_KEY={_DOTENV_FAKE_KEY}\n")

    assert _adapter(tmp_path).get_setting("llm.api_key") == "sk-from-shell"


def test_interpolation_default_fallback_when_var_unset(tmp_path, monkeypatch):
    """A ${VAR:-default} token falls back to its default when unresolved."""
    monkeypatch.delenv("TEDDY_EDITOR", raising=False)
    _write_config(tmp_path, 'editor: "${TEDDY_EDITOR:-nvim}"\n')

    assert _adapter(tmp_path).get_setting("editor") == "nvim"


def test_interpolation_unresolved_var_becomes_empty_string(tmp_path, monkeypatch):
    """An unresolved ${VAR} without a default collapses to the empty string."""
    monkeypatch.delenv("TEDDY_UNSET", raising=False)
    _write_config(tmp_path, 'editor: "before-${TEDDY_UNSET}-after"\n')

    assert _adapter(tmp_path).get_setting("editor") == "before--after"


def test_interpolation_double_dollar_escapes_literal_token(tmp_path):
    """$$ escapes the following text, yielding a literal interpolation token."""
    _write_config(tmp_path, 'editor: "$${LITERAL}"\n')

    assert _adapter(tmp_path).get_setting("editor") == "${LITERAL}"


def test_interpolation_leaves_plain_string_untouched(tmp_path):
    """A value with no interpolatable token is returned verbatim."""
    _write_config(tmp_path, 'editor: "nvim"\n')

    assert _adapter(tmp_path).get_setting("editor") == "nvim"


def test_interpolation_applies_in_exact_match_path(tmp_path, monkeypatch):
    """Interpolation also applies when the key is a top-level exact-match key."""
    monkeypatch.setenv("TEDDY_EDITOR", "code")
    _write_config(tmp_path, 'editor: "${TEDDY_EDITOR}"\n')

    assert _adapter(tmp_path).get_setting("editor") == "code"


def test_interpolation_is_live_across_transient_adapter_instances(
    tmp_path, monkeypatch
):
    """A key persisted mid-run resolves in a SECOND adapter built BEFORE the write.

    This is the same-run / cross-instance liveness guarantee: ``IConfigService``
    is registered transient (a fresh instance per resolution), so interpolation
    must read ``.teddy/.env`` fresh rather than relying on any cached value. The
    reader is constructed BEFORE the write to prove no explicit refresh is needed.
    """
    monkeypatch.delenv("TEDDY_LLM_API_KEY", raising=False)
    _write_config(tmp_path, 'llm:\n  api_key: "${TEDDY_LLM_API_KEY}"\n')

    writer = _adapter(tmp_path)
    reader = _adapter(tmp_path)  # constructed BEFORE the write
    writer.set_env_variable("TEDDY_LLM_API_KEY", "sk-written-mid-run")

    assert reader.get_setting("llm.api_key") == "sk-written-mid-run"


def test_get_setting_section_interpolates_nested_vars():
    """get_setting('llm', {}) must resolve ${VAR} tokens in child string values."""
    from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter

    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        dot_teddy = os.path.join(tmpdir, ".teddy")
        os.makedirs(dot_teddy)

        # Write .env
        env_path = os.path.join(dot_teddy, ".env")
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("TEDDY_LLM_API_KEY=sk-placeholder-xxxxxxxx\n")

        # Write config.yaml with a ${VAR} in a nested string
        config_path = os.path.join(dot_teddy, "config.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(
                "llm:\n"
                '  api_key: "${TEDDY_LLM_API_KEY}"\n'
                '  model: "openrouter/test"\n'
            )

        adapter = YamlConfigAdapter(config_path=config_path)

        # 1. Direct key access works (existing behaviour)
        assert adapter.get_setting("llm.api_key") == "sk-placeholder-xxxxxxxx", (
            "Direct nested access should interpolate"
        )

        # 2. Whole section access now also interpolates (the fix)
        llm_section = adapter.get_setting("llm", {})
        assert isinstance(llm_section, dict), "llm section must be a dict"
        assert llm_section.get("api_key") == "sk-placeholder-xxxxxxxx", (
            "Retrieving the whole llm dict should also interpolate child values"
        )
        assert llm_section.get("model") == "openrouter/test", (
            "Non-interpolated values should remain unchanged"
        )
