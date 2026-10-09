"""Contract: the bundled config.yaml declares the independent notification toggles.

Item 5 (session-behaviour): the bundled ``config.yaml`` must declare three
independent notification toggles so a user can disable the prompts drift
notification, the templates drift notification, or the update notification
independently:

    checks:
      prompts: true
      templates: true
      update: true

All default to enabled (``true``) and are read additively via
``IConfigService.get_setting`` so existing user configs (which lack the
``checks`` block) remain unaffected and behave as enabled. The ``checks.update``
toggle gates the user-facing NOTIFICATION only; the background version
fetch/caching still runs. The combined ``checks.prompts_templates`` key was
retired (the feature is unreleased, so no backward-compatibility fallback is
needed) and MUST NOT survive anywhere.
"""

from importlib import resources

import yaml


def _load_bundled_config() -> dict:
    """Load the bundled config.yaml as a parsed mapping via the package resource."""
    resource = resources.files("teddy_executor.resources.config").joinpath(
        "config.yaml"
    )
    return yaml.safe_load(resource.read_text(encoding="utf-8"))


def test_bundled_config_declares_notification_toggles():
    """The bundled config declares the three notification toggles, enabled by default."""
    config = _load_bundled_config()

    checks = config.get("checks")
    assert isinstance(checks, dict), (
        "Bundled config.yaml must declare a 'checks' mapping for notification "
        f"toggles, got: {checks!r}"
    )
    assert checks.get("prompts") is True, (
        "Bundled config.yaml must declare 'checks.prompts: true'; "
        f"got: {checks.get('prompts')!r}"
    )
    assert checks.get("templates") is True, (
        "Bundled config.yaml must declare 'checks.templates: true'; "
        f"got: {checks.get('templates')!r}"
    )
    assert checks.get("update") is True, (
        "Bundled config.yaml must declare 'checks.update: true'; "
        f"got: {checks.get('update')!r}"
    )


def test_bundled_config_retires_combined_prompts_templates_key():
    """The combined ``checks.prompts_templates`` key must be ABSENT outright."""
    config = _load_bundled_config()

    checks = config.get("checks") or {}
    assert "prompts_templates" not in checks, (
        "Bundled config.yaml must NOT declare the retired combined "
        "'checks.prompts_templates' key; got: "
        f"{checks.get('prompts_templates')!r}"
    )
