import textwrap
from pathlib import Path
from typer.testing import CliRunner
from teddy_executor.__main__ import app

runner = CliRunner()


def test_identical_find_and_replace_blocks_returns_hint(tmp_path, monkeypatch):
    """
    Scenario 1: Identical FIND and REPLACE Blocks
    Given a plan contains an EDIT action where the FIND block and REPLACE block are string-identical
    When the plan is validated
    Then a ValidationError must be returned
    And the error message must include the specific hint.
    """
    # Arrange
    # Anchor the project root to tmp_path
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".teddy").mkdir()

    target_file = Path("app.py")
    target_file.write_text("print('hello')", encoding="utf-8")

    # We use textwrap.dedent to ensure no leading indentation in the plan content.
    plan_content = textwrap.dedent("""\
        # Test Plan
        - **Status:** Green 🟢
        - **Plan Type:** Implementation
        - **Agent:** Developer

        ## Rationale
        ```text
        ### 1. Synthesis
        Testing redundant hints.

        ### 2. Justification
        Testing redundant hints.

        ### 3. Expected Outcome
        Testing redundant hints.

        ### 4. State Dashboard
        Testing redundant hints.
        ```

        ## Action Plan
        ### `EDIT`
        - **File Path:** app.py
        - **Description:** Redundant edit.

        #### `FIND:`
        ```python
        print('hello')
        ```
        #### `REPLACE:`
        ```python
        print('hello')
        ```
        """)

    # Act
    result = runner.invoke(app, ["execute", "--plan-content", plan_content])

    # Assert
    # Debug print to see output on failure
    if (
        result.exit_code == 0
        or "Hint: FIND and REPLACE blocks are identical" not in result.stdout
    ):
        print(f"\n--- CLI OUTPUT ---\n{result.stdout}\n------------------\n")

    assert result.exit_code != 0
    assert "Validation Failed" in result.stdout

    # We check for the core message, ignoring the Markdown bolding and prefix
    expected_hint = (
        "FIND and REPLACE blocks are identical. This edit can be safely omitted."
    )
    assert expected_hint in result.stdout


def test_edit_validation_hint_already_applied(tmp_path, monkeypatch):
    """
    Scenario 2: Already Applied Edit Detection
    Given a plan contains an EDIT action where the FIND block is NOT found
    And the REPLACE block IS found
    When the plan is validated
    Then the error message must include the "Already Applied" hint.
    """
    # Arrange
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".teddy").mkdir()

    target_file = Path("app.py")
    # Content already has the "REPLACE" block but not the "FIND" block
    target_file.write_text(
        "def hello():\n    print('Hello pytest')\n", encoding="utf-8"
    )

    plan_content = textwrap.dedent("""\
        # Test Plan
        - **Status:** Green 🟢
        - **Plan Type:** Implementation
        - **Agent:** Developer

        ## Rationale
        ```text
        ### 1. Synthesis
        Testing already applied hint.

        ### 2. Justification
        Testing already applied hint.

        ### 3. Expected Outcome
        Testing already applied hint.

        ### 4. State Dashboard
        Testing already applied hint.
        ```

        ## Action Plan
        ### `EDIT`
        - **File Path:** app.py
        - **Description:** This edit has already been applied.

        #### `FIND:`
        ```python
        def hello():
            print('Hello world')
        ```
        #### `REPLACE:`
        ```python
        def hello():
            print('Hello pytest')
        ```
        """)

    # Act
    result = runner.invoke(app, ["execute", "--plan-content", plan_content])

    # Assert
    assert result.exit_code != 0
    assert "Validation Failed" in result.stdout
    assert "The `FIND` block could not be located" in result.stdout
    expected_hint = "The FIND block was not found, but the REPLACE block is already present. This change might have already been applied."
    assert expected_hint in result.stdout
