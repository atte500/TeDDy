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
    assert (
        guard.should_continue(turn_count=1, cumulative_cost=0.0, interactive=True)
        is True
    )


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

    guard = ProductionSessionLoopGuard(
        config_service=mock_config, initial_turn=1, initial_cost=0.0
    )

    # Act / Assert
    # delta = 5 (>= limit 5) -> STOP
    assert (
        guard.should_continue(turn_count=6, cumulative_cost=0.0, interactive=False)
        is False
    )
    # delta = 4 (< limit 5) -> CONTINUE
    assert (
        guard.should_continue(turn_count=5, cumulative_cost=0.0, interactive=False)
        is True
    )


def test_production_guard_stops_on_max_cost_non_interactive():
    # Arrange
    mock_config = create_autospec(IConfigService)
    mock_config.get_setting.side_effect = lambda key, default=None: (
        1.50 if key == "yolo_guardrails.max_session_cost" else default
    )

    guard = ProductionSessionLoopGuard(
        config_service=mock_config, initial_turn=1, initial_cost=1.00
    )

    # Act / Assert
    # delta = 1.50 (>= limit 1.50) -> STOP
    assert (
        guard.should_continue(turn_count=1, cumulative_cost=2.50, interactive=False)
        is False
    )
    # delta = 1.49 (< limit 1.50) -> CONTINUE
    assert (
        guard.should_continue(turn_count=1, cumulative_cost=2.49, interactive=False)
        is True
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
    assert (
        guard.should_continue(turn_count=100, cumulative_cost=100.0, interactive=True)
        is True
    )
