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
