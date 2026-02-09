from pathlib import Path
from textwrap import dedent

from .helpers import run_cli_with_plan


def test_edit_action_replaces_verbatim_without_smart_indent(
    monkeypatch, tmp_path: Path
):
    """
    Given a plan to perform a multiline edit,
    When the find block is an exact match (including indentation),
    And the replace block contains its own correct indentation,
    Then the file should be updated by replacing the find block
    verbatim with the replace block, without any extra indentation logic.
    """
    # Arrange
    file_to_edit = tmp_path / "my_class.py"
    original_content = dedent(
        """\
        class MyClass:
            def __init__(self, value):
                self.value = value

            def existing_method(self):
                \"\"\"An existing method.\"\"\"
                return self.value
        """
    )
    file_to_edit.write_text(original_content)

    # The find block is an EXACT, character-for-character match of the
    # target text in the source file, including its leading indentation.
    find_block = (
        "    def existing_method(self):\n"
        '        """An existing method."""\n'
        "        return self.value"
    )

    # The replace block is also provided with its exact, final indentation,
    # as required by the new, simplified contract.
    replace_block = (
        "    def updated_method(self, multiplier):\n"
        '        """An updated method."""\n'
        "        return self.value * multiplier"
    )

    plan = [
        {
            "action": "edit",
            "description": "Test multiline edit with verbatim replacement.",
            "params": {
                "path": str(file_to_edit),
                "find": find_block,
                "replace": replace_block,
            },
        }
    ]

    # The expected content is the original content with a simple,
    # verbatim replacement of the find block with the replace block.
    expected_content = (
        dedent(
            """\
        class MyClass:
            def __init__(self, value):
                self.value = value

        """
        )
        + replace_block
        + "\n"
    )

    # Act
    result = run_cli_with_plan(monkeypatch, plan, tmp_path)

    # Assert
    assert result.exit_code == 0, f"CLI command failed: {result.stdout}"

    actual_content = file_to_edit.read_text()

    # We strip trailing whitespace to make the comparison robust.
    # The key assertion is that the indentation of the block itself is correct.
    assert actual_content.strip() == expected_content.strip()
