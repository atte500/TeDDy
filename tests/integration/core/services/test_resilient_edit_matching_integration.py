from textwrap import dedent
from typer.testing import CliRunner
from teddy_executor.__main__ import app

runner = CliRunner()


def test_fuzzy_edit_success_with_diff_in_report(tmp_path, monkeypatch):
    """
    Scenario: Successful fuzzy match should inject a diff into the report.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".teddy").mkdir()
    target_file = tmp_path / "app.py"
    target_file.write_text("def hello():\n    print('hello world')\n", encoding="utf-8")

    # FIND block has minor whitespace difference (extra space at end of line)
    plan = dedent("""\
        # Test Plan
        - Status: Green 🟢
        - Plan Type: Implementation
        - Agent: Developer

        ## Rationale
        ```text
        ### 1. Synthesis
        Previous turn was successful.
        ### 2. Justification
        The user wants to update the greeting.
        ### 3. Expected Outcome
        The greeting will be 'hello universe'.
        ### 4. State Dashboard
        - Task: Update greeting
        ```

        ## Action Plan

        ### `EDIT`
        - File Path: [app.py](/app.py)
        - Description: Update hello world.

        #### `FIND:`
        ```python
        def hello():
            print('hello world')
        ```
        #### `REPLACE:`
        ```python
        def hello():
            print('hello universe')
        ```
        """)
    result = runner.invoke(app, ["execute", "--plan-content", plan, "--yes"])

    assert result.exit_code == 0
    # Check that the file was updated
    assert "hello universe" in target_file.read_text(encoding="utf-8")
    # Check that a diff was injected into the report (stdout/clipboard)
    assert "--- a/app.py" in result.stdout
    assert "+++ b/app.py" in result.stdout
    assert "-    print('hello world')" in result.stdout
    assert "+    print('hello universe')" in result.stdout


def test_edit_custom_threshold_fail(tmp_path, monkeypatch):
    """
    Scenario: EDIT should fail if the match score is below a custom threshold.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".teddy").mkdir()
    target_file = tmp_path / "app.py"
    target_file.write_text("def hello():\n    print('hello world')\n", encoding="utf-8")

    # Threshold set to 0.99, while the match (with extra space) will be around 0.95-0.98
    plan = dedent("""\
        # Test Plan
        - Status: Green 🟢
        - Plan Type: Implementation
        - Agent: Developer

        ## Rationale
        ```text
        ### 1. Synthesis
        Previous turn was successful.
        ### 2. Justification
        The user wants to update the greeting with a high precision requirement.
        ### 3. Expected Outcome
        The greeting will be updated or fail if precision is not met.
        ### 4. State Dashboard
        - Task: Update greeting
        ```

        ## Action Plan

        ### `EDIT`
        - File Path: [app.py](/app.py)
        - Similarity Threshold: 0.99
        - Description: Update hello world.

        #### `FIND:`
        ```python
        def hello():
            print('hello world')
        ```
        #### `REPLACE:`
        ```python
        def hello():
            print('hello universe')
        ```
        """)
    result = runner.invoke(app, ["execute", "--plan-content", plan, "--yes"])

    assert result.exit_code != 0
    assert "The `FIND` block could not be located" in result.stdout
    assert "Similarity Score" in result.stdout
    assert "Similarity Threshold: 0.99" in result.stdout


def test_edit_ambiguity_tie_fail(tmp_path, monkeypatch):
    """
    Scenario: EDIT should fail if two blocks match with the same highest score.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".teddy").mkdir()
    target_file = tmp_path / "app.py"
    target_file.write_text(
        "def block1():\n    pass\n\ndef block2():\n    pass\n", encoding="utf-8"
    )

    # FIND block matches both block1 and block2 with same similarity score
    plan = dedent("""\
        # Test Plan
        - Status: Green 🟢
        - Plan Type: Implementation
        - Agent: Developer

        ## Rationale
        ```text
        ### 1. Synthesis
        Previous turn was successful.
        ### 2. Justification
        The user wants an ambiguous update.
        ### 3. Expected Outcome
        The update should fail due to ambiguity.
        ### 4. State Dashboard
        - Task: Ambiguous update
        ```

        ## Action Plan

        ### `EDIT`
        - File Path: [app.py](/app.py)
        - Description: Ambiguous update.

        #### `FIND:`
        ```python
        def block_match():
            pass
        ```
        #### `REPLACE:`
        ```python
        def block_match():
            print('done')
        ```
        """)
    result = runner.invoke(app, ["execute", "--plan-content", plan, "--yes"])

    assert result.exit_code != 0
    assert "ambiguous" in result.stdout.lower()
    assert "Similarity Score" in result.stdout
