import pytest
from teddy_executor.core.services.validation_rules.edit_matcher import find_best_match


@pytest.mark.parametrize(
    "file_indent, find_indent, expected_offset",
    [
        (4, 0, 4),  # AI provided no indent, file has 4
        (8, 4, 4),  # AI provided 4, file has 8
        (2, 4, -2),  # AI provided 4, file has 2 (negative offset)
        (0, 0, 0),  # Exact match
    ],
)
def test_matcher_detects_constant_indentation_offset(
    file_indent, find_indent, expected_offset
):
    file_content = (
        f"{' ' * file_indent}print('line 1')\n{' ' * file_indent}print('line 2')"
    )
    find_block = (
        f"{' ' * find_indent}print('line 1')\n{' ' * find_indent}print('line 2')"
    )

    _, score, _, offset = find_best_match(file_content, find_block)

    assert score == 1.0
    assert offset == expected_offset


def test_matcher_ignores_empty_lines_for_offset_calculation():
    file_content = "    line1\n\n    line2"
    find_block = "line1\n\nline2"  # Offset 4

    _, score, _, offset = find_best_match(file_content, find_block)

    assert score == 1.0
    assert offset == 4


def test_matcher_requires_consistent_offset_across_all_code_lines():
    file_content = "    line1\n    line2"
    find_block = "  line1\nline2"  # Offsets: 2, 4

    _, score, _, offset = find_best_match(file_content, find_block)

    assert score < 1.0
    assert offset == 0
