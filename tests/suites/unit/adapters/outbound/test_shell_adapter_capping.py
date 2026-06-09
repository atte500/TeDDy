from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter


def test_shell_adapter_truncates_stdout_to_max_lines():
    # Arrange
    # We pass the limit via constructor (to be implemented)
    max_lines = 3
    adapter = ShellAdapter(max_execute_lines=max_lines)

    large_output = "line1\nline2\nline3\nline4\nline5"

    # Act
    # Testing the processing logic directly
    result = adapter._process_execution_results(large_output, "", 0)

    # Assert
    lines = result["stdout"].splitlines()
    # The result should be: [Hint] + last 3 lines = 4 lines total
    assert len(lines) == max_lines + 1
    assert "[Output truncated" in lines[0]
    assert "line3" in lines[1]
    assert "line4" in lines[2]
    assert "line5" in lines[3]


def test_shell_adapter_does_not_truncate_if_under_limit():
    # Arrange
    max_lines = 10
    adapter = ShellAdapter(max_execute_lines=max_lines)
    output = "line1\nline2"

    # Act
    result = adapter._process_execution_results(output, "", 0)

    # Assert
    assert result["stdout"] == output
    assert "[Output truncated" not in result["stdout"]


def test_shell_adapter_process_execution_results_with_max_lines_override():
    """Verifies that passing max_lines override to _process_execution_results
    overrides the adapter's default max_execute_lines."""
    # Arrange
    adapter = ShellAdapter(max_execute_lines=100)
    large_output = "line1\nline2\nline3\nline4\nline5"

    # Act
    # max_lines=3 should override the default 100
    result = adapter._process_execution_results(large_output, "", 0, max_lines=3)

    # Assert
    lines = result["stdout"].splitlines()
    assert len(lines) == 4  # Hint line + last 3 lines
    assert "[Output truncated" in lines[0]
    assert "line3" in lines[1]
    assert "line4" in lines[2]
    assert "line5" in lines[3]
