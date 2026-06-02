import pytest
from teddy_executor.core.services.session_loop_guard import ProductionSessionLoopGuard


def test_production_loop_guard_requires_three_arguments():
    # Arrange
    guard = ProductionSessionLoopGuard()

    # Act / Assert
    # Verify it fails with old signature (1 arg)
    with pytest.raises(TypeError):
        guard.should_continue(1)

    # Verify it succeeds with new signature (3 args)
    assert (
        guard.should_continue(turn_count=1, cumulative_cost=0.0, interactive=True)
        is True
    )
