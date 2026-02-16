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
    assert "--- src/main.py ---" in output
    # Smart fencing uses 3 backticks for simple content
    assert "```python\nprint('hello')\n```" in output
    assert "--- README.md ---" in output
    assert "```markdown\n# Title\n```" in output
    assert "--- missing.txt (Not Found) ---" in output

    # 6. Check order of headers
    assert (
        output.find("# System Information")
        < output.find("# Repository Tree")
        < output.find("# Context Vault")
        < output.find("# File Contents")
    )
