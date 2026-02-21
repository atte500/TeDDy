from pathlib import Path
from textwrap import dedent

from .helpers import run_cli_with_markdown_plan_on_clipboard
from .plan_builder import MarkdownPlanBuilder


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
    file_to_edit.write_text(original_content, encoding="utf-8")

    # The find_block must be an exact substring of the original content,
    # including the correct indentation. Using dedent here was creating
    # an unindented string that could not be found.
    find_block = (
        "    def existing_method(self):\n"
        '        """An existing method."""\n'
        "        return self.value"
    )

    # The replace block also needs to have the correct indentation.
    replace_block = (
        "    def updated_method(self, multiplier):\n"
        '        """An updated method."""\n'
        "        return self.value * multiplier"
    )

    builder = MarkdownPlanBuilder("Test Multiline Edit")
    builder.add_action(
        "EDIT",
        params={
            "File Path": f"[{file_to_edit.name}](/{file_to_edit.name})",
            "Description": "Test multiline edit with verbatim replacement.",
        },
        content_blocks={
            "`FIND:`": ("python", find_block),
            "`REPLACE:`": ("python", replace_block),
        },
    )
    plan_content = builder.build()

    expected_content = dedent(
        """\
        class MyClass:
            def __init__(self, value):
                self.value = value

            def updated_method(self, multiplier):
                \"\"\"An updated method.\"\"\"
                return self.value * multiplier
        """
    )

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code == 0, f"CLI command failed: {result.stdout}"
    actual_content = file_to_edit.read_text()
    assert actual_content.strip() == expected_content.strip()


def test_empty_replace_removes_newline(monkeypatch, tmp_path: Path):
    """
    Scenario 3: An `EDIT` action with an empty `REPLACE` block leaves no orphaned empty line.
    """
    # Arrange
    file_to_edit = tmp_path / "target.txt"
    original_content = dedent(
        """\
        Line 1
        Line 2
        Line 3
        """
    )
    file_to_edit.write_text(original_content, encoding="utf-8")

    builder = MarkdownPlanBuilder("Test Clean Deletion")
    builder.add_action(
        "EDIT",
        params={
            "File Path": f"[{file_to_edit.name}](/{file_to_edit.name})",
            "Description": "Delete middle line",
        },
        content_blocks={
            "`FIND:`": ("text", "Line 2"),
            "`REPLACE:`": ("text", ""),
        },
    )
    plan_content = builder.build()

    # The expected output should not have an empty line between 1 and 3.
    expected_content = dedent(
        """\
        Line 1
        Line 3
        """
    )

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code == 0, f"CLI command failed: {result.stdout}"
    actual_content = file_to_edit.read_text(encoding="utf-8")
    assert actual_content == expected_content
