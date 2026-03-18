from teddy_executor.core.services.validation_rules.edit_matcher import (
    find_best_match_and_diff,
)


def test_matcher_returns_score_and_ambiguity():
    content = "def hello():\n    print('world')\n"
    # Exact match should have score 1.0 and not be ambiguous
    find_block = "def hello():\n    print('world')\n"
    diff, score, is_ambiguous = find_best_match_and_diff(
        content, find_block, threshold=0.8
    )

    assert score == 1.0
    assert is_ambiguous is False
    assert (
        diff == ""
    )  # Exact match returns empty diff in current implementation or similar


def test_matcher_detects_ambiguity_on_tie():
    content = "block\nblock\n"
    find_block = "block\n"
    # Both 'block\n' instances are identical, so it should be ambiguous
    diff, score, is_ambiguous = find_best_match_and_diff(
        content, find_block, threshold=0.8
    )

    assert is_ambiguous is True
    assert score == 1.0


def test_matcher_respects_custom_threshold():
    content = "def hello():\n    print('world')\n"
    # Minor difference: 'word' instead of 'world'
    find_block = "def hello():\n    print('word')\n"

    # Threshold 0.99 should fail validation, but find_best_match_and_diff
    # should still provide a diff to aid the user in debugging.
    high_threshold = 0.99
    diff, score, is_ambiguous = find_best_match_and_diff(
        content, find_block, threshold=high_threshold
    )
    assert score < high_threshold
    assert diff != ""

    # Threshold 0.8 should succeed
    low_threshold = 0.8
    diff, score, is_ambiguous = find_best_match_and_diff(
        content, find_block, threshold=low_threshold
    )
    assert score >= low_threshold
    assert diff != ""


def test_matcher_surgical_substring_boost():
    """Verify that single-line FIND blocks return ONLY the matching substring."""
    from teddy_executor.core.services.validation_rules.edit_matcher import (
        find_best_match,
    )

    content = "The quick brown fox jumps over the lazy dog."
    find_block = "brown fox"

    match_str, score, is_ambiguous = find_best_match(content, find_block)

    assert score == 1.0
    assert match_str == "brown fox"
    assert is_ambiguous is False


def test_matcher_rounds_score_to_two_decimal_places():
    """Verify that similarity scores are rounded to 2 decimal places."""
    from teddy_executor.core.services.validation_rules.edit_matcher import (
        find_best_match,
    )

    # 'The quick brown fox' (19 chars)
    # 'The quick brown fix' (19 chars)
    # 18 chars match. Ratio = 2*18 / (19+19) = 36/38 = 0.947368...
    content = "The quick brown fox"
    find_block = "The quick brown fix"

    _, score, _ = find_best_match(content, find_block)

    # Should be rounded to 0.95
    expected_rounded_score = 0.95
    assert score == expected_rounded_score
