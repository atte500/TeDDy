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
