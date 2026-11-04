"""Contract coverage for the matcher decision record and its legacy adapters.

``find_best_match_ex`` exposes the complete decision for one FIND block: the
winning text, the raw similarity score, the ambiguity verdict, the indentation
offset, the runner-up score, and the number of refined candidates at or above
the threshold. ``find_best_match`` and ``find_best_match_and_diff`` keep their
four-value tuple contract and derive every value from that same record.
"""

import pytest

from teddy_executor.core.services.validation_rules.edit_matcher import (
    MatchResult,
    find_best_match,
    find_best_match_and_diff,
    find_best_match_ex,
)

_SINGLE_CONTENT = "def hello():\n    print('world')\n"
_TIE_CONTENT = "foo bar\nfoo bar\nfoo bar\n"
_TIE_FIND = "foo baz"
_TIE_SCORE = 0.80
_FUZZY_CONTENT = "The quick brown fox"
_FUZZY_FIND = "The quick brown fix"


def test_decision_record_exposes_all_six_fields():
    record = find_best_match_ex(_SINGLE_CONTENT, _SINGLE_CONTENT)

    assert isinstance(record, MatchResult)
    assert record.match == _SINGLE_CONTENT
    assert record.score == 1.0
    assert record.is_ambiguous is False
    assert record.offset == 0
    assert record.runner_up == 0.0
    assert record.candidate_count == 1


def test_decision_record_reports_runner_up_and_candidate_count():
    record = find_best_match_ex(_TIE_CONTENT, _TIE_FIND, threshold=_TIE_SCORE)

    assert record.score == pytest.approx(_TIE_SCORE)
    assert record.runner_up == pytest.approx(_TIE_SCORE)
    assert record.candidate_count == 3
    assert record.is_ambiguous is True


def test_decision_record_keeps_raw_score_while_legacy_adapter_rounds():
    record = find_best_match_ex(_FUZZY_CONTENT, _FUZZY_FIND)
    match, score, is_ambiguous, offset = find_best_match(_FUZZY_CONTENT, _FUZZY_FIND)

    assert record.score == pytest.approx(36 / 38)
    assert round(record.score, 2) == 0.95
    assert (match, score, is_ambiguous, offset) == (
        record.match,
        round(record.score, 2),
        record.is_ambiguous,
        record.offset,
    )


def test_diff_entry_point_gates_the_diff_on_the_rounded_score():
    content = "x" * 400 + "\n"
    find = "x" * 399 + "y"

    diff, score, _, _ = find_best_match_and_diff(content, find)

    assert score == 1.0
    assert diff == ""
