"""Contract coverage for exact candidate counting in the matcher decision record.

Every scored candidate reaches refinement, so ``candidate_count`` reports the
real number of windows at or above the similarity threshold instead of a
truncated five. The refinement cap only ever truncated that count: the winning
window and its raw score are unchanged wherever the pool already fit inside the
retired cap.
"""

import pytest

from teddy_executor.core.services.validation_rules.edit_matcher import (
    find_best_match_ex,
)
from tests.harness.setup.edit_scenarios import repeated_function, sibling_function


@pytest.mark.parametrize("copies", [7, 12])
def test_candidate_count_is_exact_beyond_the_retired_cap(copies):
    content = repeated_function("compute", copies)

    record = find_best_match_ex(content, sibling_function("computa"))

    assert record.candidate_count == copies
    assert record.score < 1.0
    assert record.runner_up == pytest.approx(record.score)
    assert record.is_ambiguous is True


def test_cap_removal_keeps_the_winning_block_text():
    content = repeated_function("compute", 7)

    record = find_best_match_ex(content, sibling_function("computa"))

    assert record.match == sibling_function("compute")
