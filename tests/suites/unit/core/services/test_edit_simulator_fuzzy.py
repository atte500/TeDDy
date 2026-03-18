import pytest
from teddy_executor.core.services.edit_simulator import EditSimulator
from teddy_executor.core.domain.models import (
    MultipleMatchesFoundError,
    SearchTextNotFoundError,
)


def test_simulate_edits_fuzzy_success():
    simulator = EditSimulator()
    content = "def hello():\n    print('world')\n"
    # Minor discrepancy (extra space)
    edits = [{"find": "def hello(): ", "replace": "def greeting():"}]

    # Should succeed with threshold 0.8
    result, _ = simulator.simulate_edits(content, edits, threshold=0.8)
    assert "def greeting():" in result
    assert "print('world')" in result


def test_simulate_edits_fuzzy_fail_threshold():
    simulator = EditSimulator()
    content = "def hello():\n    print('world')\n"
    edits = [{"find": "def hello(): ", "replace": "def greeting():"}]

    # Should fail with high threshold 0.99
    with pytest.raises(SearchTextNotFoundError) as excinfo:
        simulator.simulate_edits(content, edits, threshold=0.99)
    assert "Best Score" in str(excinfo.value)


def test_simulate_edits_fuzzy_ambiguous():
    simulator = EditSimulator()
    content = "block1\nblock2\n"
    # 'block' matches both similarly
    edits = [{"find": "block", "replace": "new"}]

    with pytest.raises(MultipleMatchesFoundError) as excinfo:
        simulator.simulate_edits(content, edits)
    assert "ambiguous" in str(excinfo.value).lower()
