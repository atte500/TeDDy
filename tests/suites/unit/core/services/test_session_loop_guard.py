from unittest.mock import create_autospec
from teddy_executor.core.ports.outbound import IConfigService
from teddy_executor.core.services.session_loop_guard import ProductionSessionLoopGuard


def test_production_guard_always_continues():
    # Arrange
    mock_config = create_autospec(IConfigService)
    guard = ProductionSessionLoopGuard(
        config_service=mock_config, initial_turn=1, initial_cost=0.0
    )

    # Act / Assert
    assert guard.should_continue(
        turn_count=1, cumulative_cost=0.0, interactive=True
    ) == (True, None)


def test_production_guard_stores_initial_state():
    # Arrange
    mock_config = create_autospec(IConfigService)
    initial_turn = 5
    initial_cost = 1.25

    # Act
    guard = ProductionSessionLoopGuard(
        config_service=mock_config, initial_turn=initial_turn, initial_cost=initial_cost
    )

    # Assert
    assert guard._initial_turn == initial_turn
    assert guard._initial_cost == initial_cost


def test_production_guard_stops_on_max_turns_non_interactive():
    # Arrange
    mock_config = create_autospec(IConfigService)
    mock_config.get_setting.side_effect = lambda key, default=None: (
        5 if key == "yolo_guardrails.max_turns" else default
    )
    mock_config.get_config_path.return_value = ".teddy/config.yaml"

    guard = ProductionSessionLoopGuard(
        config_service=mock_config, initial_turn=1, initial_cost=0.0
    )

    # Act / Assert
    # delta = 5 (>= limit 5) -> STOP
    should_continue, reason = guard.should_continue(
        turn_count=6, cumulative_cost=0.0, interactive=False
    )
    assert should_continue is False
    assert reason is not None
    assert "max_turns" in reason
    assert ".teddy/config.yaml" in reason
    assert "5/5" in reason
    # delta = 4 (< limit 5) -> CONTINUE
    assert guard.should_continue(
        turn_count=5, cumulative_cost=0.0, interactive=False
    ) == (True, None)


def test_production_guard_stops_on_max_cost_non_interactive():
    # Arrange
    mock_config = create_autospec(IConfigService)
    mock_config.get_setting.side_effect = lambda key, default=None: (
        1.50 if key == "yolo_guardrails.max_session_cost" else default
    )
    mock_config.get_config_path.return_value = ".teddy/config.yaml"

    guard = ProductionSessionLoopGuard(
        config_service=mock_config, initial_turn=1, initial_cost=1.00
    )

    # Act / Assert
    # delta = 1.50 (>= limit 1.50) -> STOP
    should_continue, reason = guard.should_continue(
        turn_count=1, cumulative_cost=2.50, interactive=False
    )
    assert should_continue is False
    assert reason is not None
    assert "max_session_cost" in reason
    assert ".teddy/config.yaml" in reason
    assert "$1.50/$1.50" in reason
    # delta = 1.49 (< limit 1.50) -> CONTINUE
    assert guard.should_continue(
        turn_count=1, cumulative_cost=2.49, interactive=False
    ) == (True, None)


def test_production_guard_reason_includes_config_key_and_path():
    """
    Verify that when a turn‑limit stop occurs the reason mentions
    the config key yolo_guardrails.max_turns and includes the config file path.
    """
    # Arrange
    mock_config = create_autospec(IConfigService)
    mock_config.get_setting.side_effect = lambda key, default=None: (
        1 if key == "yolo_guardrails.max_turns" else default
    )
    mock_config.get_config_path.return_value = ".teddy/config.yaml"

    guard = ProductionSessionLoopGuard(
        config_service=mock_config, initial_turn=1, initial_cost=0.0
    )

    # Act – delta = 1 (>= limit 1) -> STOP
    should_continue, reason = guard.should_continue(
        turn_count=2, cumulative_cost=0.0, interactive=False
    )

    # Assert – currently fails because reason is "YOLO guardrail limit reached."
    assert should_continue is False
    assert "yolo_guardrails.max_turns" in reason, (
        f"Reason should mention the config key, got: {reason!r}"
    )
    assert ".teddy/config.yaml" in reason, (
        f"Reason should include the config file path, got: {reason!r}"
    )


def test_production_guard_ignores_limits_in_interactive_mode():
    # Arrange
    mock_config = create_autospec(IConfigService)
    mock_config.get_setting.side_effect = lambda key, default=None: (
        1 if key == "yolo_guardrails.max_turns" else default
    )

    guard = ProductionSessionLoopGuard(
        config_service=mock_config, initial_turn=1, initial_cost=0.0
    )

    # Act / Assert
    # Limits reached but interactive -> CONTINUE
    assert guard.should_continue(
        turn_count=100, cumulative_cost=100.0, interactive=True
    ) == (True, None)
