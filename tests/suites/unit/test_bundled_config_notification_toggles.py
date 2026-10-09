"""Contract: the bundled config.yaml declares the independent notification toggles.

Item 5 (session-behaviour): the bundled ``config.yaml`` must declare two
independent notification toggles so a user can disable either the prompts/
templates drift notification or the update notification:

    checks:
      prompts_templates: true
      update: true

Both default to enabled (``true``) and are read additively via
``IConfigService.get_setting`` so existing user configs (which lack the
``checks`` block) remain unaffected and behave as enabled. The ``checks.update``
toggle gates the user-facing NOTIFICATION only; the background version
fetch/caching still runs.
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
    """The bundled config declares both notification toggles, enabled by default."""
    config = _load_bundled_config()

    checks = config.get("checks")
    assert isinstance(checks, dict), (
        "Bundled config.yaml must declare a 'checks' mapping for notification "
        f"toggles, got: {checks!r}"
    )
    assert checks.get("prompts_templates") is True, (
        "Bundled config.yaml must declare 'checks.prompts_templates: true'; "
        f"got: {checks.get('prompts_templates')!r}"
    )
    assert checks.get("update") is True, (
        "Bundled config.yaml must declare 'checks.update: true'; "
        f"got: {checks.get('update')!r}"
    )
