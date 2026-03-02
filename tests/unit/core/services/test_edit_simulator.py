import pytest
from teddy_executor.core.services.edit_simulator import EditSimulator
from teddy_executor.core.domain.models import (
    SearchTextNotFoundError,
    MultipleMatchesFoundError,
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
    result = simulator.simulate_edits(content, edits)

    # Then
    assert result == "LINE ONE\nline 2\nLINE THREE"


def test_simulate_edits_raises_error_if_find_not_found():
    content = "line 1\nline 2"
    edits = [{"find": "missing", "replace": "replacement"}]
    simulator = EditSimulator()

    with pytest.raises(SearchTextNotFoundError):
        simulator.simulate_edits(content, edits)


def test_simulate_edits_raises_error_if_find_is_ambiguous():
    content = "duplicate\nduplicate"
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

    result = simulator.simulate_edits(content, edits)

    assert result == "Line 1\nLine 3\n"
