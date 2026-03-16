from teddy_executor.core.services.edit_simulator import EditSimulator


def test_simulate_edits_returns_scores():
    """
    Asserts that simulate_edits returns a tuple of (content, scores).
    """
    simulator = EditSimulator()
    content = "hello world"
    edits = [{"find": "hello", "replace": "bye"}]

    # This is expected to fail or return only string in the current implementation
    result = simulator.simulate_edits(content, edits)

    # We want a result object or tuple
    assert isinstance(result, tuple)
    new_content, scores = result
    assert new_content == "bye world"
    assert scores == [1.0]


def test_simulate_edits_bulk_replacement():
    """
    Asserts that replace_all=True replaces all occurrences.
    """
    simulator = EditSimulator()
    content = "a a a"
    edits = [{"find": "a", "replace": "b"}]

    # Currently it only replaces one. We want it to handle a replace_all flag.
    # Note: I'll need to update the EditPair TypedDict in the port as well.
    new_content, scores = simulator.simulate_edits(content, edits, replace_all=True)

    assert new_content == "b b b"
    # For bulk edits, we might return a list of scores or an average.
    # Scenario 5 says "respect similarity threshold for each match".
    # Let's assume we return a list of scores for that specific edit.
    assert scores == [1.0]
