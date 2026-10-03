"""Regression pin for the removal of the ``ui_mode`` special-case in the harness config mock.

With the console plan reviewer gone, no production code reads a ``ui_mode``
config key, so the test harness's ``IConfigService`` mock MUST behave like an
ordinary default-returning setting lookup rather than special-casing ``ui_mode``.
"""

from teddy_executor.core.ports.outbound import IConfigService

from tests.harness.setup.test_environment import TestEnvironment


def test_harness_config_mock_returns_caller_default_for_ui_mode(monkeypatch):
    env = TestEnvironment(monkeypatch)
    try:
        env.setup()
        config = env.get_service(IConfigService)

        assert config.get_setting("ui_mode", default="sentinel") == "sentinel"
    finally:
        env.teardown()


def test_harness_config_mock_returns_disabled_for_editor(monkeypatch):
    """The harness config mock pins ``editor`` to the ``"disabled"`` sentinel.

    Preflight editor validation reads ``get_setting("editor")``; resolving the
    sentinel by default makes that validation inert for CLI-driving tests, so
    the editor gate never blocks them. Tests that exercise editor behaviour
    override the setting explicitly (e.g. ``_configure_editor``).
    """
    env = TestEnvironment(monkeypatch)
    try:
        env.setup()
        config = env.get_service(IConfigService)

        assert config.get_setting("editor") == "disabled"
        # Every other key still mirrors IConfigService.get_setting.
        assert config.get_setting("some_other_key", default="sentinel") == "sentinel"
    finally:
        env.teardown()
