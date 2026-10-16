"""Unit tests: the guard's limit resolution and message-turn baseline reset.

The guard resolves each limit through a precedence chain (CLI flag over
environment variable over config value over default). It reads the renamed
``guardrails`` namespace with a legacy ``yolo_guardrails`` fallback, defaults
the turn limit to 150, and re-anchors its baselines after a message turn when
``guardrails.message_reset`` is enabled.
"""

from unittest.mock import create_autospec

from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.services.session_loop_guard import ProductionSessionLoopGuard


def _guard(config_values=None, env_values=None, **overrides):
    """Builds a guard wired to in-memory config and environment doubles."""
    config = create_autospec(IConfigService)
    settings = config_values or {}
    config.get_setting.side_effect = lambda key, default=None: settings.get(
        key, default
    )
    config.get_config_path.return_value = ".teddy/config.yaml"

    environment = create_autospec(ISystemEnvironment)
    variables = env_values or {}
    environment.get_env.side_effect = lambda key: variables.get(key)

    return ProductionSessionLoopGuard(
        config_service=config,
        system_environment=environment,
        initial_turn=0,
        initial_cost=0.0,
        **overrides,
    )


def test_cli_flag_wins_over_environment_and_config():
    """The CLI flag outranks the environment value and the config value."""
    guard = _guard(
        config_values={"guardrails.max_turns": 50},
        env_values={"TEDDY_MAX_TURNS": "20"},
        max_turns=3,
    )
    assert guard.should_continue(2, 0.0, False) == (True, None)
    assert guard.should_continue(3, 0.0, False)[0] is False


def test_environment_overrides_config_value():
    """The environment value outranks the config value."""
    guard = _guard(
        config_values={"guardrails.max_turns": 50},
        env_values={"TEDDY_MAX_TURNS": "2"},
    )
    assert guard.should_continue(1, 0.0, False) == (True, None)
    assert guard.should_continue(2, 0.0, False)[0] is False


def test_config_value_used_without_cli_or_environment():
    """The config value applies when neither a flag nor an env var is present."""
    guard = _guard(config_values={"guardrails.max_turns": 4})
    assert guard.should_continue(3, 0.0, False) == (True, None)
    assert guard.should_continue(4, 0.0, False)[0] is False


def test_legacy_key_used_when_renamed_key_absent():
    """The legacy yolo_guardrails key applies when guardrails is absent."""
    guard = _guard(config_values={"yolo_guardrails.max_turns": 6})
    assert guard.should_continue(5, 0.0, False) == (True, None)
    assert guard.should_continue(6, 0.0, False)[0] is False


def test_default_turn_limit_is_150():
    """The turn limit defaults to 150 when no source supplies a value."""
    guard = _guard()
    assert guard.should_continue(149, 0.0, False) == (True, None)
    assert guard.should_continue(150, 0.0, False)[0] is False


def test_environment_overrides_cost_limit():
    """The cost environment override outranks the config value."""
    guard = _guard(env_values={"TEDDY_MAX_SESSION_COST": "1.00"})
    assert guard.should_continue(1, 0.99, False) == (True, None)
    assert guard.should_continue(1, 1.00, False)[0] is False


def test_default_cost_limit_is_five_dollars():
    """The cost limit defaults to five dollars when no source supplies a value."""
    guard = _guard()
    assert guard.should_continue(1, 4.99, False) == (True, None)
    assert guard.should_continue(1, 5.00, False)[0] is False


def test_reset_baseline_re_anchors_turn_and_cost():
    """reset_baseline re-anchors both baselines for the next segment."""
    guard = _guard(
        config_values={"guardrails.max_turns": 3, "guardrails.max_session_cost": 2.0}
    )
    guard.reset_baseline(turn_count=10, cumulative_cost=1.5)
    assert guard.should_continue(11, 1.6, False) == (True, None)
    assert guard.should_continue(13, 1.6, False)[0] is False


def test_reset_disabled_leaves_baselines_fixed():
    """A disabled message_reset leaves the original baselines in force."""
    guard = _guard(config_values={"guardrails.message_reset": False})
    guard.reset_baseline(turn_count=10, cumulative_cost=1.5)
    assert guard.should_continue(149, 0.0, False) == (True, None)
    assert guard.should_continue(150, 0.0, False)[0] is False
