from teddy_executor.core.services.validation_rules.helpers import is_path_in_context


def test_is_path_in_context_empty():
    assert is_path_in_context("path", {}) is False
    assert is_path_in_context("", {"Turn": ["path"]}) is False


def test_is_path_in_context_normalizes_slashes():
    """
    Scenario: Context contains Windows paths (backslashes),
    but plan uses forward slashes (TeDDy standard).
    """
    # Arrange
    context_paths = {"Turn": ["src\\logic.py", "docs\\spec.md"]}

    # Act / Assert
    # 1. Forward slash target finds backslash context
    assert is_path_in_context("src/logic.py", context_paths) is True

    # 2. Backslash target finds backslash context
    assert is_path_in_context("src\\logic.py", context_paths) is True

    # 3. Mixed target finds backslash context
    assert is_path_in_context("/src/logic.py", context_paths) is True


def test_is_path_in_context_respects_scopes():
    # Arrange
    context_paths = {"Session": ["session_file.txt"], "Turn": ["turn_file.txt"]}

    # Act / Assert
    assert (
        is_path_in_context(
            "session_file.txt", context_paths, check_session=True, check_turn=False
        )
        is True
    )
    assert (
        is_path_in_context(
            "session_file.txt", context_paths, check_session=False, check_turn=True
        )
        is False
    )
    assert (
        is_path_in_context(
            "turn_file.txt", context_paths, check_session=True, check_turn=False
        )
        is False
    )
    assert (
        is_path_in_context(
            "turn_file.txt", context_paths, check_session=False, check_turn=True
        )
        is True
    )
