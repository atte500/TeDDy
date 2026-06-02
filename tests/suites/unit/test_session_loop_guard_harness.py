import pytest


def test_mock_session_loop_guard_is_registered(mock_session_loop_guard):
    """
    Verify that the mock_session_loop_guard fixture is available and
    properly specced against ISessionLoopGuard.
    """
    # Assert
    assert hasattr(mock_session_loop_guard, "should_continue")

    # Verify auto-spec is working (should fail if we try to call non-existent method)
    with pytest.raises(AttributeError):
        mock_session_loop_guard.non_existent_method()
