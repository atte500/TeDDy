from teddy_executor.adapters.inbound.cli_formatter import (
    format_project_context,
)
from teddy_executor.core.domain.models import ContextResult


def test_format_project_context():
    """
    Given a ContextResult DTO,
    When format_project_context is called,
    Then it should return a string with the four required sections in order,
    and with the correct content and formatting.
    """
    # Arrange
    context = ContextResult(
        system_info={"os": "test_os", "shell": "/bin/test", "python_version": "3.x"},
        repo_tree="src/\n  main.py",
        context_vault_paths=["src/main.py", "README.md", "missing.txt"],
        file_contents={
            "src/main.py": "print('hello')",
            "README.md": "# Title",
            "missing.txt": None,
        },
    )

    # Act
    output = format_project_context(context)

    # Assert
    # 1. Check for all four headers
    assert "# System Information" in output
    assert "# Repository Tree" in output
    assert "# Context Vault" in output
    assert "# File Contents" in output

    # 2. Check content of System Information
    # Note: python_version should be excluded
    assert "os: test_os" in output
    assert "shell: /bin/test" in output
    assert "python_version" not in output

    # 3. Check content of Repository Tree
    assert "src/\n  main.py" in output

    # 4. Check content of Context Vault (clean list)
    assert "```" not in output.split("# Context Vault")[1].split("# File Contents")[0]
    assert "src/main.py" in output
    assert "README.md" in output

    # 5. Check content of File Contents
    assert "## [src/main.py](/src/main.py)" in output
    # Smart fencing uses 3 backticks for simple content
    assert "```python\nprint('hello')\n```" in output
    assert "## [README.md](/README.md)" in output
    assert "```markdown\n# Title\n```" in output
    assert "## missing.txt (Not Found)" in output

    # 6. Check order of headers
    assert (
        output.find("# System Information")
        < output.find("# Repository Tree")
        < output.find("# Context Vault")
        < output.find("# File Contents")
    )


def test_format_project_context_uses_smart_fencing():
    """
    Given a ContextResult with file content containing triple backticks,
    When format_project_context is called,
    Then the output should use a fence of at least 4 backticks for that file.
    """
    # GIVEN
    file_content_with_backticks = "Here is a code block:\n```python\nprint('hi')\n```"

    context = ContextResult(
        system_info={"os": "Linux"},
        repo_tree=".",
        context_vault_paths=["README.md"],
        file_contents={"README.md": file_content_with_backticks},
    )

    # WHEN
    result = format_project_context(context)

    # THEN
    # We look for the file header
    assert "## [README.md](/README.md)" in result
    # And we expect a smart fence (quad backticks)
    assert "````markdown" in result or "````" in result
    assert file_content_with_backticks in result

    # Specifically ensure we don't have triple backticks as the fence
    # (since the content has triple backticks, using triple backticks as fence would be ambiguous/wrong)
    # Ideally, we check for exact structural match.
    # Note: cli_formatter adds extension. README.md -> .md -> markdown
    expected_segment_with_lang = (
        "````markdown\nHere is a code block:\n```python\nprint('hi')\n```\n````"
    )

    assert expected_segment_with_lang in result


def test_format_project_context_uses_smart_fencing_deep():
    """
    Given a ContextResult with file content containing QUAD backticks,
    When format_project_context is called,
    Then the output should use a fence of at least 5 backticks.
    """
    # GIVEN
    file_content = "Deep nesting:\n````\ncode\n````"

    context = ContextResult(
        system_info={},
        repo_tree=".",
        context_vault_paths=["deep.txt"],
        file_contents={"deep.txt": file_content},
    )

    # WHEN
    result = format_project_context(context)

    # THEN
    # We expect 5 backticks
    assert "`````" in result
    assert file_content in result
