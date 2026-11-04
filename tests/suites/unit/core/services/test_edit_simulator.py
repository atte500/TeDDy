import pytest
from teddy_executor.core.services.edit_simulator import EditSimulator
from teddy_executor.core.domain.models import (
    SearchTextNotFoundError,
    MultipleMatchesFoundError,
)
from tests.harness.setup.edit_scenarios import (
    INDENTATION_ONLY_DUPLICATE,
    VERBATIM_DUPLICATE,
)


def test_simulate_edits_applies_multiple_pairs_sequentially():
    # Given
    content = "line 1\nline 2\nline 3"
    edits = [
        {"find": "line 1", "replace": "LINE ONE"},
        {"find": "line 3", "replace": "LINE THREE"},
    ]
    simulator = EditSimulator()

    # When
    result, scores = simulator.simulate_edits(content, edits)

    # Then
    assert result == "LINE ONE\nline 2\nLINE THREE"
    assert all(s == 1.0 for s in scores)


def test_simulate_edits_raises_error_if_find_not_found():
    content = "line 1\nline 2"
    edits = [{"find": "missing", "replace": "replacement"}]
    simulator = EditSimulator()

    with pytest.raises(SearchTextNotFoundError):
        simulator.simulate_edits(content, edits)


def test_simulate_edits_raises_error_if_find_is_ambiguous():
    # Use content where both occurrences are identical including newlines
    content = "duplicate\nduplicate\n"
    edits = [{"find": "duplicate", "replace": "unique"}]
    simulator = EditSimulator()

    with pytest.raises(MultipleMatchesFoundError):
        simulator.simulate_edits(content, edits)


def test_simulate_edits_removes_newline_on_empty_replacement():
    """
    Verifies that an empty REPLACE block removes the associated newline
    to prevent orphaned empty lines.
    """
    content = "Line 1\nLine 2\nLine 3\n"
    edits = [{"find": "Line 2", "replace": ""}]
    simulator = EditSimulator()

    result, _ = simulator.simulate_edits(content, edits)

    assert result == "Line 1\nLine 3\n"


@pytest.mark.parametrize(
    "scenario",
    [INDENTATION_ONLY_DUPLICATE, VERBATIM_DUPLICATE],
    ids=["indentation_only_duplicate", "verbatim_duplicate"],
)
def test_ambiguity_message_reports_the_candidate_count(scenario):
    simulator = EditSimulator()

    with pytest.raises(MultipleMatchesFoundError) as excinfo:
        simulator.simulate_edits(
            scenario.content,
            [{"find": scenario.find, "replace": "    return 0\n"}],
        )

    assert "Found 2 ambiguous candidates" in str(excinfo.value)
