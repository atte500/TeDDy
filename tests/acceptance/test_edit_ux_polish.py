from .helpers import run_execute_with_plan_content
import textwrap


def test_multi_edit_ux_polish(monkeypatch, tmp_path):
    """
    Scenario: Multi-edit plan where one match is perfect and one is fuzzy.
    Expect:
    1. Similarity score list is shown correctly.
    2. Fuzzy match has character-level diff (ndiff style).
    3. Proper whitespace in report.
    """
    target_file = tmp_path / "code.py"
    # Create the fuzzy discrepancy: file has 'line_two  =  2', plan asks for 'line_two = 2'
    target_file.write_text("line_one = 1\nline_two  =  2\n")

    plan_content = textwrap.dedent("""\
        # UX Polish Plan
        - **Status:** Green 🟢
        - **Agent:** Developer
        - **Plan Type:** Implementation

        ## Rationale
        ```text
        ### 1. Synthesis
        Testing diff UX.

        ### 2. Justification
        TDD for UX polish.

        ### 3. Expected Outcome
        Fuzzy match and report.

        ### 4. State Dashboard
        [✓] Test
        ```

        ## Action Plan

        ### `EDIT`
        - **File Path:** [code.py](/code.py)
        - **Similarity Threshold:** 0.8
        - **Description:** Apply perfect and fuzzy edits.

        #### `FIND:`
        ```python
        line_one = 1
        ```
        #### `REPLACE:`
        ```python
        line_one = "perfect"
        ```

        #### `FIND:`
        ```python
        line_two = 2
        ```
        #### `REPLACE:`
        ```python
        line_two = 2.0
        ```
    """)
    result = run_execute_with_plan_content(monkeypatch, plan_content, tmp_path)

    assert result.exit_code == 0
    report = result.stdout

    # 1. Similarity Scores should show both (0.89 remains roughly correct for 'line_two  =  2' vs 'line_two = 2')
    assert "**Similarity Scores:** 1.00, 0.89" in report

    # 2. Check for ndiff markers
    assert "?" in report  # Character level marker
    assert "- line_two  =  2" in report
    assert "+ line_two = 2.0" in report

    # 3. Check whitespace (#### diff should be preceded by a newline)
    assert "#### `diff`" in report
    # Ensure it's not jammed against the previous line
    assert "\n#### `diff`" in report


def test_perfect_edit_suppresses_diff(monkeypatch, tmp_path):
    """Scenario: All edits are 1.0, #### diff should be missing."""
    target_file = tmp_path / "clean.py"
    # Ensure exact match by matching the whole content if necessary, or stripping newline
    target_file.write_text("hello")

    plan_content = textwrap.dedent("""\
        # Perfect Plan
        - **Status:** Green 🟢
        - **Agent:** Developer
        - **Plan Type:** Implementation

        ## Rationale
        ```text
        ### 1. Synthesis
        Perfect match test.
        ### 2. Justification
        Verify suppression.
        ### 3. Expected Outcome
        No diff.
        ### 4. State Dashboard
        [✓] Done
        ```

        ## Action Plan

        ### `EDIT`
        - **File Path:** [clean.py](/clean.py)
        - **Description:** Perfect edit.

        #### `FIND:`
        ```
        hello
        ```
        #### `REPLACE:`
        ```
        world
        ```
    """)
    result = run_execute_with_plan_content(monkeypatch, plan_content, tmp_path)
    assert result.exit_code == 0
    assert "#### `diff`" not in result.stdout
    assert "**Similarity Score:** 1.00" in result.stdout
