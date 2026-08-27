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


def test_mock_session_loop_guard_returns_tuple(mock_session_loop_guard):
    """
    Verify that the auto-specced mock fixture returns a tuple (bool, str | None)
    matching the updated ISessionLoopGuard contract.
    """
    result = mock_session_loop_guard.should_continue(1, 0.0, False)

    assert isinstance(result, tuple), f"Expected tuple, got {type(result)}: {result!r}"
    assert len(result) == 2
    assert isinstance(result[0], bool)
    assert result[1] is None or isinstance(result[1], str)
