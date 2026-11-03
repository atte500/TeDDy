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


def test_edit_simulator_drops_replace_terminator_for_intra_line_fragment():
    """
    A single-line FIND block carries an authored trailing newline but matches an
    intra-line fragment. The matcher drops the FIND terminator from the match, so
    the REPLACE terminator must be dropped too; otherwise the terminator is
    injected mid-line and the file is corrupted.
    """
    content = "Hello, world!"
    edits = [{"find": "world\n", "replace": "TeDDy\n"}]
    simulator = EditSimulator()

    result, _ = simulator.simulate_edits(content, edits)

    assert result == "Hello, TeDDy!"


def test_edit_simulator_bulk_replacement_drops_replace_terminator_per_fragment():
    """
    match_all replacement with single-line FIND/REPLACE blocks that carry
    authored trailing newlines. Each intra-line fragment match must not inject
    the REPLACE terminator mid-line.
    """
    content = "DEBUG: start\nDEBUG: middle\nDEBUG: end\n"
    edits = [{"find": "DEBUG:\n", "replace": "INFO:\n"}]
    simulator = EditSimulator()

    result, _ = simulator.simulate_edits(content, edits, match_all=True)

    assert result == "INFO: start\nINFO: middle\nINFO: end\n"


def test_edit_simulator_preserves_authored_newline_on_full_line_match():
    """
    A full-line FIND match that carries an authored trailing newline keeps the
    REPLACE's authored newline verbatim.
    """
    content = "old\nsecond\n"
    edits = [{"find": "old\n", "replace": "new\n"}]
    simulator = EditSimulator()

    result, _ = simulator.simulate_edits(content, edits)

    assert result == "new\nsecond\n"
