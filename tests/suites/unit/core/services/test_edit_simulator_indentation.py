from teddy_executor.core.services.edit_simulator import EditSimulator


def test_simulator_applies_positive_indentation_offset_to_replace_block():
    """
    If file has 4 spaces and AI provided 0, offset is +4.
    REPLACE block should be indented by 4 spaces.
    """
    simulator = EditSimulator()
    content = "    def hello():\n        print('old')"
    find = "def hello():\n    print('old')"  # 4 spaces relative to content
    replace = "def hello():\n    print('new')"

    # find_best_match will return offset=4
    new_content, scores = simulator.simulate_edits(
        content, [{"find": find, "replace": replace}]
    )

    expected = "    def hello():\n        print('new')"
    assert new_content == expected
    assert scores == [1.0]


def test_simulator_applies_negative_indentation_offset_to_replace_block():
    """
    If file has 0 spaces and AI provided 4, offset is -4.
    REPLACE block should be de-indented by 4 spaces.
    """
    simulator = EditSimulator()
    content = "def hello():\nprint('old')"
    find = "    def hello():\n    print('old')"  # -4 offset
    replace = "    def hello():\n    print('new')"

    new_content, scores = simulator.simulate_edits(
        content, [{"find": find, "replace": replace}]
    )

    expected = "def hello():\nprint('new')"
    assert new_content == expected
    assert scores == [1.0]


def test_simulator_preserves_empty_lines_during_indentation_adjustment():
    simulator = EditSimulator()
    content = "    line1\n\n    line2"
    find = "line1\n\nline2"  # offset 4
    replace = "new1\n\nnew2"

    new_content, _ = simulator.simulate_edits(
        content, [{"find": find, "replace": replace}]
    )

    assert new_content == "    new1\n\n    new2"
