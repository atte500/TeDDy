"""Unit: the config-success banner renders the CANONICAL agent name.

Item 6 (session-behaviour): the startup banner must display the canonical
agent form (first letter uppercase, remainder lowercase) so ``-a PATHFINDER``
renders as ``Agent: Pathfinder`` -- matching the persisted ``agent_name`` and
the ``Waiting for <Agent> to respond...`` planning header.
"""

import pytest

from teddy_executor.adapters.inbound.session_cli_handlers import _echo_config_success
from teddy_executor.core.ports.outbound.config_service import IConfigService


@pytest.mark.parametrize(
    ("raw_agent", "expected_agent"),
    [
        ("PATHFINDER", "Pathfinder"),
        ("pathfinder", "Pathfinder"),
        ("DeVeLoPeR", "Developer"),
    ],
)
def test_echo_config_success_canonicalises_displayed_agent_name(
    env, capsys, raw_agent, expected_agent
):
    """The banner displays the canonical agent form, never the raw input."""
    config_service = env.mock_port(IConfigService)
    config_service.get_setting.return_value = (
        "openrouter/deepseek/deepseek-v4-pro:nitro"
    )

    # Act
    _echo_config_success(env.container, agent=raw_agent)

    # Assert
    captured = capsys.readouterr()
    assert f"Agent: {expected_agent}" in captured.err, (
        f"Expected canonical 'Agent: {expected_agent}' in banner, got: "
        f"{captured.err.strip()!r}"
    )
