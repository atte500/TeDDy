import textwrap
from typer.testing import CliRunner
from teddy_executor.__main__ import app

runner = CliRunner()


def test_edit_reports_similarity_score_on_success(monkeypatch, tmp_path):
    """
    Scenario 5.1: Success Transparency
    GIVEN a file and an EDIT action that matches exactly
    WHEN executed
    THEN the report should include the Similarity Score: 1.00
    """
    # Create project root marker
    (tmp_path / ".teddy").mkdir()
    monkeypatch.chdir(tmp_path)

    target_file = tmp_path / "app.py"
    target_file.write_text("print('hello')\n", encoding="utf-8")

    plan = textwrap.dedent("""\
        # Success Transparency
        - **Status:** Green 🟢
        - **Plan Type:** Implementation
        - **Agent:** Dev

        ## Rationale
        ```text
        ### 1. Synthesis
        Testing transparency.

        ### 2. Justification
        Testing.

        ### 3. Expected Outcome
        Success.

        ### 4. State Dashboard
        - Status: OK
        ```

        ## Action Plan

        ### `EDIT`
        - **File Path:** [app.py](/app.py)
        - **Description:** Perfect match

        #### `FIND:`
        ```python
        print('hello')
        ```
        #### `REPLACE:`
        ```python
        print('world')
        ```
        """)

    result = runner.invoke(app, ["execute", "--plan-content", plan, "--yes"])
    assert result.exit_code == 0
    assert "**Similarity Score:** 1.00" in result.stdout
    assert target_file.read_text(encoding="utf-8") == "print('world')\n"


def test_edit_bulk_replacement(monkeypatch, tmp_path):
    """
    Scenario 5.2: Multi-Instance Replacement
    GIVEN a file with multiple occurrences of a string
    WHEN an EDIT action with 'Replace All: true' is executed
    THEN all occurrences should be replaced
    AND the report should show the similarity score
    """
    (tmp_path / ".teddy").mkdir()
    monkeypatch.chdir(tmp_path)

    target_file = tmp_path / "multi.py"
    content = "DEBUG: start\nDEBUG: middle\nDEBUG: end\n"
    target_file.write_text(content, encoding="utf-8")

    plan = textwrap.dedent("""\
        # Bulk Replace
        - **Status:** Green 🟢
        - **Plan Type:** Implementation
        - **Agent:** Dev

        ## Rationale
        ```text
        ### 1. Synthesis
        Testing bulk replacement.

        ### 2. Justification
        Testing.

        ### 3. Expected Outcome
        Success.

        ### 4. State Dashboard
        - Status: OK
        ```

        ## Action Plan

        ### `EDIT`
        - **File Path:** [multi.py](/multi.py)
        - **Replace All:** true
        - **Description:** Replace all DEBUG logs

        #### `FIND:`
        ```python
        DEBUG:
        ```
        #### `REPLACE:`
        ```python
        INFO:
        ```
        """)

    result = runner.invoke(app, ["execute", "--plan-content", plan, "--yes"])
    assert result.exit_code == 0

    # Verify file content
    expected = "INFO: start\nINFO: middle\nINFO: end\n"
    assert target_file.read_text(encoding="utf-8") == expected

    # Verify reporting
    assert "**Similarity Score:** 1.00" in result.stdout
    assert "**Replace All:** True" in result.stdout


def test_edit_ambiguity_hint_update(monkeypatch, tmp_path):
    """
    Scenario 5.3: Improved Ambiguity Hint
    GIVEN a file with multiple occurrences
    WHEN an EDIT action is attempted without 'Replace All'
    THEN validation should fail with an improved hint
    """
    (tmp_path / ".teddy").mkdir()
    monkeypatch.chdir(tmp_path)

    target_file = tmp_path / "ambiguous.py"
    target_file.write_text("dup\ndup\n", encoding="utf-8")

    plan = textwrap.dedent("""\
        # Ambiguity Hint
        - **Status:** Green 🟢
        - **Plan Type:** Implementation
        - **Agent:** Dev

        ## Rationale
        ```text
        ### 1. Synthesis
        Testing hint.

        ### 2. Justification
        Testing.

        ### 3. Expected Outcome
        Success.

        ### 4. State Dashboard
        - Status: OK
        ```

        ## Action Plan

        ### `EDIT`
        - **File Path:** [ambiguous.py](/ambiguous.py)
        - **Description:** Ambiguous edit

        #### `FIND:`
        ```python
        dup
        ```
        #### `REPLACE:`
        ```python
        changed
        ```
        """)

    result = runner.invoke(app, ["execute", "--plan-content", plan, "--yes"])

    # Should fail validation
    assert "The `FIND` block is ambiguous" in result.stdout
    assert (
        "and to use Replace All: true if intention is to change all occurrences in the file"
        in result.stdout
    )
