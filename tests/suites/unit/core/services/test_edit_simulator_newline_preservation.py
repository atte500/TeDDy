from teddy_executor.core.services.edit_simulator import EditSimulator


def test_edit_simulator_preserves_crlf_line_endings():
    """
    Scenario 3: Line Ending Preservation (CRLF).
    Verify that if the matched block ends with CRLF, the replacement also uses CRLF.
    """
    # Use explicit CRLF
    content = "Line 1\r\nLine 2\r\nLine 3\r\n"
    edits = [{"find": "Line 2", "replace": "REPLACED"}]
    simulator = EditSimulator()

    result, _ = simulator.simulate_edits(content, edits)

    # The entire file should maintain CRLF, and the replacement should have CRLF appended
    expected = "Line 1\r\nREPLACED\r\nLine 3\r\n"
    assert expected == result
    assert "\r\n" in result
    assert result.count("\r\n") == expected.count("\r\n")
    assert "\n" not in result.replace("\r\n", "")  # No stray LFs


def test_edit_simulator_preserves_lf_line_endings():
    """
    Verify that standard LF is still preserved correctly.
    """
    content = "Line 1\nLine 2\nLine 3\n"
    edits = [{"find": "Line 2", "replace": "REPLACED"}]
    simulator = EditSimulator()

    result, _ = simulator.simulate_edits(content, edits)

    assert "Line 1\nREPLACED\nLine 3\n" == result
    assert "\r\n" not in result
