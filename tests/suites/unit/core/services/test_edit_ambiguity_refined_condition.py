"""Contract coverage for the refined ambiguity rule over the canonical scenarios.

The refined rule treats a FIND block as ambiguous when two candidates tie at or
above the similarity threshold, or when a sub-verbatim winner (no verbatim and
no indentation-only promotion) still has a runner-up at or above the threshold.
A verbatim winner beside a near-duplicate sibling stays accepted, and a single
true location whose shifted start falls below the floor stays accepted.

Every scenario comes from ``tests.harness.setup.edit_scenarios`` so the fixture
text lives in one place.
"""

from teddy_executor.core.domain.models.plan import DEFAULT_SIMILARITY_THRESHOLD
from teddy_executor.core.services.validation_rules.edit import _validate_single_edit
from teddy_executor.core.services.validation_rules.edit_matcher import (
    find_best_match,
    find_best_match_and_diff,
    find_best_match_ex,
)
from tests.harness.setup.edit_scenarios import (
    FUZZY_NEAR_TIE,
    INDENTATION_ONLY_DUPLICATE,
    REPEATING_INNER_LINE,
    VERBATIM_VS_NEAR_DUPLICATE,
)

_REPLACE = "    return 0\n"


def _validate(content: str, find: str, match_all: bool = False):
    return _validate_single_edit(
        {"find": find, "replace": _REPLACE},
        content,
        "sample.py",
        DEFAULT_SIMILARITY_THRESHOLD,
        match_all=match_all,
    )


def test_fuzzy_near_tie_is_ambiguous():
    record = find_best_match_ex(FUZZY_NEAR_TIE.content, FUZZY_NEAR_TIE.find)

    assert record.score < 1.0
    assert record.runner_up >= DEFAULT_SIMILARITY_THRESHOLD
    assert record.runner_up < record.score
    assert record.candidate_count == 2
    assert record.is_ambiguous is True


def test_legacy_entry_points_surface_the_refined_verdict():
    _, score, is_ambiguous, _ = find_best_match(
        FUZZY_NEAR_TIE.content, FUZZY_NEAR_TIE.find
    )
    diff, diff_score, diff_ambiguous, _ = find_best_match_and_diff(
        FUZZY_NEAR_TIE.content, FUZZY_NEAR_TIE.find
    )

    assert is_ambiguous is True
    assert diff_ambiguous is True
    assert diff == ""
    assert diff_score == score


def test_verbatim_winner_beside_a_near_duplicate_sibling_is_accepted():
    record = find_best_match_ex(
        VERBATIM_VS_NEAR_DUPLICATE.content, VERBATIM_VS_NEAR_DUPLICATE.find
    )

    assert record.score == 1.0
    assert record.runner_up >= DEFAULT_SIMILARITY_THRESHOLD
    assert record.is_ambiguous is False


def test_indentation_promoted_duplicate_is_ambiguous():
    record = find_best_match_ex(
        INDENTATION_ONLY_DUPLICATE.content, INDENTATION_ONLY_DUPLICATE.find
    )

    assert record.score == 1.0
    assert record.candidate_count == 2
    assert record.is_ambiguous is True


def test_single_location_with_a_shifted_start_is_accepted():
    record = find_best_match_ex(REPEATING_INNER_LINE.content, REPEATING_INNER_LINE.find)

    assert record.score < 1.0
    assert record.runner_up < DEFAULT_SIMILARITY_THRESHOLD
    assert record.is_ambiguous is False


def test_validator_reports_the_fuzzy_near_tie_as_ambiguous():
    errors = _validate(FUZZY_NEAR_TIE.content, FUZZY_NEAR_TIE.find)

    assert len(errors) == 1
    message = errors[0].message
    assert "ambiguous" in message.lower()
    assert FUZZY_NEAR_TIE.find in message


def test_match_all_bypasses_the_refined_verdict():
    assert _validate(FUZZY_NEAR_TIE.content, FUZZY_NEAR_TIE.find, match_all=True) == []
