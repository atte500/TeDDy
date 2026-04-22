"""
Regression test for whitespace-indifferent matching in EditMatcher.
"""

from teddy_executor.core.services.validation_rules.edit_matcher import find_best_match


def test_find_best_match_ignores_trailing_whitespace_on_intermediate_lines():
    """
    Reproduces the issue where trailing whitespace on intermediate lines
    causes a similarity score < 1.0 despite identical code logic.
    """
    # File content with trailing spaces and tabs on various lines
    file_content = (
        "def example_func():  \n"  # Trailing spaces
        "    # Step 1: Arrange  \t\n"  # Trailing tab
        "    setup_something()\n"  # Clean
        "    return True  \n"  # Trailing spaces
    )

    # AI-generated FIND block (clean)
    find_block = (
        "def example_func():\n"
        "    # Step 1: Arrange\n"
        "    setup_something()\n"
        "    return True"
    )

    match_str, score, is_ambiguous, offset = find_best_match(file_content, find_block)

    # Assertions
    # Current behavior: score is approx 0.93-0.95
    # Desired behavior: score is exactly 1.0
    assert score == 1.0, (
        f"Expected perfect match (1.0), got {score}. Match found: {match_str!r}"
    )
    assert not is_ambiguous


def test_find_best_match_allows_relative_indentation():
    """
    Ensures that relative indentation (constant offset) is treated as a perfect match.
    """
    file_content = "    print('hello')\n    print('world')"
    find_block = "print('hello')\nprint('world')"

    _, score, _, offset = find_best_match(file_content, find_block)

    # Score should be 1.0 because the offset (+4) is constant
    assert score == 1.0
    assert offset == 4


def test_find_best_match_rejects_inconsistent_relative_indentation():
    """
    Ensures that if relative indentation is NOT constant, it is not boosted to 1.0.
    """
    file_content = "    print('hello')\n    print('world')"
    find_block = "  print('hello')\nprint('world')"  # Offsets: 2 and 4

    _, score, _, _ = find_best_match(file_content, find_block)

    assert score < 1.0


def test_find_best_match_respects_logic_differences():
    """
    Ensures that significant code differences are NOT ignored.
    """
    file_content = "def func():\n    return False"
    find_block = "def func():\n    return True"

    _, score, _, _ = find_best_match(file_content, find_block)

    assert score < 1.0, f"Logic change should not receive 1.0 bonus. Got {score}"
