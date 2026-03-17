import textwrap
from .helpers import run_execute_with_plan_content


def test_multi_block_edit_shows_all_diffs(monkeypatch, tmp_path):
    """
    Scenario: Single EDIT action with two separate FIND/REPLACE blocks.
    Expect: The execution report should show diffs for BOTH changes.
    """
    # Set global threshold to 0.8 for fuzzy matching in this test
    (tmp_path / ".teddy").mkdir(exist_ok=True)
    (tmp_path / ".teddy" / "config.yaml").write_text("similarity_threshold: 0.8\n")

    target_file = tmp_path / "multi_site.py"
    # Large gap to trigger hunk separation
    content = ["site_one  =  1"] + ["# line"] * 10 + ["site_two  =  2"]
    target_file.write_text("\n".join(content) + "\n")

    plan_content = textwrap.dedent("""\
        # Multi-Site Plan
        - **Status:** Green 🟢
        - **Agent:** Developer
        - **Plan Type:** Implementation

        ## Rationale
        ```text
        ### 1. Synthesis
        Testing multi-site transparency with fuzzy matches and hunks.
        ### 2. Justification
        Verify both edits show in report with hunks.
        ### 3. Expected Outcome
        Two diff segments separated by '...'.
        ### 4. State Dashboard
        [✓] Test
        ```

        ## Action Plan

        ### `EDIT`
        - **File Path:** [multi_site.py](/multi_site.py)
        - **Similarity Threshold:** 0.8
        - **Description:** Edit two sites.

        #### `FIND:`
        ```python
        site_one = 1
        ```
        #### `REPLACE:`
        ```python
        site_one = 1.0
        ```

        #### `FIND:`
        ```python
        site_two = 2
        ```
        #### `REPLACE:`
        ```python
        site_two = 2.0
        ```
    """)
    result = run_execute_with_plan_content(monkeypatch, plan_content, tmp_path)
    assert result.exit_code == 0
    report = result.stdout

    # Verify both changes are in the diff
    assert "- site_one  =  1" in report
    assert "+ site_one = 1.0" in report
    assert "- site_two  =  2" in report
    assert "+ site_two = 2.0" in report
    assert "?" in report
    assert "..." in report
