from teddy_executor.core.services.validation_rules.edit_matcher import (
    find_best_match,
    LARGE_BLOCK_LINE_LIMIT,
)


def test_matcher_gives_indifference_bonus_for_small_blocks_missing_newline():
    """
    Scenario 1: Small Block.
    Verify that an exact content match receives a 1.0 score even if the trailing newline is missing.
    """
    content = "print('hello')\n"
    find_block = "print('hello')"  # Missing newline

    match_str, score, is_ambiguous = find_best_match(content, find_block)

    assert score == 1.0
    assert match_str == "print('hello')\n"
    assert is_ambiguous is False


def test_matcher_gives_indifference_bonus_for_small_blocks_with_crlf():
    """
    Verify that CRLF line endings are also handled by the indifference bonus.
    """
    content = "print('hello')\r\n"
    find_block = "print('hello')"  # Missing CRLF

    match_str, score, is_ambiguous = find_best_match(content, find_block)

    assert score == 1.0
    assert match_str == "print('hello')\r\n"


def test_matcher_gives_indifference_bonus_for_large_blocks_missing_newline():
    """
    Scenario 2: Large Block.
    Verify that large blocks (> LARGE_BLOCK_LINE_LIMIT) also receive the bonus.
    """
    # Create a block larger than the limit
    lines = [f"line {i}" for i in range(LARGE_BLOCK_LINE_LIMIT + 5)]
    content = "\n".join(lines) + "\n"
    find_block = "\n".join(lines)  # Missing the final newline

    match_str, score, is_ambiguous = find_best_match(content, find_block)

    # This is expected to FAIL until Scenario 2 is implemented
    assert score == 1.0
    assert match_str == content
