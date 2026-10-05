"""Regression coverage for EDIT ambiguity detection gated on the effective threshold.

The edit matcher previously flagged *any* tie between candidate windows as
"ambiguous" regardless of how low the similarity score was. Because the
validator checked ambiguity *before* the threshold, a FIND block that barely
matched anything produced a misleading:

    The `FIND` block is ambiguous

error with no diff guidance, instead of the actionable:

    The `FIND` block could not be located

error that includes the Closest Match Diff.

These tests pin the corrected contract:
  * a tie below the effective threshold is treated as "not found";
  * a tie at or above the effective threshold is treated as "ambiguous";
and they guard against regressing to a hard-coded threshold.
"""

from teddy_executor.core.domain.models.plan import ValidationError
from teddy_executor.core.services.validation_rules.edit import _validate_single_edit
from teddy_executor.core.services.validation_rules.edit_matcher import (
    find_best_match_and_diff,
)

# Three identical windows produce a three-way tie at the same similarity score.
_CONTENT = "foo bar\nfoo bar\nfoo bar\n"
_FIND = "foo baz"
_TIE_SCORE = 0.80
_STRICT_THRESHOLD = 0.95


def _classify(errors: list[ValidationError]) -> str:
    if not errors:
        return "success"
    message = errors[0].message.lower()
    if "ambiguous" in message:
        return "ambiguous"
    if "could not be located" in message:
        return "not_found"
    return "other"


def _validate(find: str, threshold: float) -> list[ValidationError]:
    return _validate_single_edit(
        {"find": find, "replace": "replacement"},
        _CONTENT,
        "sample.txt",
        threshold,
        match_all=False,
    )


# ---------------------------------------------------------------------------
# Matcher-level contracts
# ---------------------------------------------------------------------------


def test_matcher_low_score_tie_is_not_ambiguous():
    """A tie below the threshold is merely a bad match, not an ambiguous one."""
    _, score, is_ambiguous, _ = find_best_match_and_diff(
        _CONTENT, _FIND, threshold=_STRICT_THRESHOLD
    )
    assert score < _STRICT_THRESHOLD
    assert is_ambiguous is False


def test_matcher_tie_at_threshold_is_ambiguous():
    """A tie meeting the effective threshold is genuinely ambiguous."""
    _, score, is_ambiguous, _ = find_best_match_and_diff(
        _CONTENT, _FIND, threshold=_TIE_SCORE
    )
    assert score >= _TIE_SCORE
    assert is_ambiguous is True


# ---------------------------------------------------------------------------
# Validator-level contracts (observable error messages)
# ---------------------------------------------------------------------------


def test_low_score_tie_reports_not_found_with_diff():
    """A sub-threshold tie must surface the 'not found' error with a diff."""
    errors = _validate(_FIND, _STRICT_THRESHOLD)

    assert _classify(errors) == "not_found"
    assert "Closest Match Diff" in errors[0].message


def test_tie_at_threshold_reports_ambiguous():
    """A tie meeting the effective threshold must surface the 'ambiguous' error."""
    errors = _validate(_FIND, _TIE_SCORE)

    assert _classify(errors) == "ambiguous"
