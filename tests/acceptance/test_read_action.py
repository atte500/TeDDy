from pathlib import Path
from pytest_httpserver import HTTPServer

from .helpers import run_teddy_with_stdin


def test_read_local_file_successfully(tmp_path: Path):
    """
    Scenario 1: Read a local file successfully
    Given a file exists with known content,
    When the teddy executor is run with a plan to read the file,
    Then the execution report indicates success and contains the file's content.
    """
    # Arrange: Create a source file with known content
    source_file = tmp_path / "source.txt"
    expected_content = "Hello, TeDDy!"
    source_file.write_text(expected_content)

    # Act: Run teddy with a plan to read the file
    plan = f"""
    - action: read
      params:
        source: "{source_file}"
    """
    result = run_teddy_with_stdin(plan, cwd=tmp_path)
    output = result.stdout
    print(f"\n--- TEDDY STDOUT ---\n{output}\n--- END TEDDY STDOUT ---")

    # Assert
    assert "Execution Report" in output
    assert f"### Action: `read` (`{source_file}`)" in output
    assert "- **Status:** SUCCESS" in output
    assert "Hello, TeDDy!" in output
    assert "```" in output


def test_read_non_existent_local_file_fails(tmp_path: Path):
    """
    Scenario 2: Fail to read a non-existent local file
    Given no file exists at a certain path,
    When the teddy executor is run with a plan to read that path,
    Then the execution report indicates failure and contains a 'File not found' error.
    """
    # Arrange
    non_existent_file = tmp_path / "non_existent.txt"
    plan = f"""
    - action: read
      params:
        source: "{non_existent_file}"
    """

    # Act
    result = run_teddy_with_stdin(plan, cwd=Path("."))
    output = result.stdout
    print(f"\n--- TEDDY STDOUT ---\n{output}\n--- END TEDDY STDOUT ---")

    # Assert
    assert "Run Summary: FAILURE" in output
    assert f"### Action: `read` (`{non_existent_file}`)" in output
    assert "status: FAILURE" in output
    assert "No such file or directory" in output


def test_read_remote_url_successfully(httpserver: HTTPServer):
    """
    Scenario 3: Read a remote URL successfully
    Given a valid and accessible URL,
    When the teddy executor is run with a plan to read the URL,
    Then the execution report indicates success and contains the page content.
    """
    # Arrange
    # The server will respond with HTML
    html_content = "<h1>Test Header</h1><p>Test paragraph.</p>"
    # The test will assert that the output is Markdown
    expected_markdown_content = "Test Header\n===========\n\nTest paragraph."
    httpserver.expect_request("/test-page").respond_with_data(html_content)
    test_url = httpserver.url_for("/test-page")

    plan = f"""
    - action: read
      params:
        source: "{test_url}"
    """

    # Act
    result = run_teddy_with_stdin(plan, cwd=Path("."))
    output = result.stdout

    # Assert
    assert "Run Summary: SUCCESS" in output
    assert f"### Action: `read` (`{test_url}`)" in output
    assert "- **Status:** SUCCESS" in output
    assert expected_markdown_content in output


def test_read_inaccessible_remote_url_fails(httpserver: HTTPServer):
    """
    Scenario 4: Fail to read an inaccessible remote URL
    Given a URL that returns a 404 error,
    When the teddy executor is run with a plan to read that URL,
    Then the execution report indicates failure and contains a '404' error message.
    """
    # Arrange
    httpserver.expect_request("/not-found").respond_with_data("Not Found", status=404)
    test_url = httpserver.url_for("/not-found")
    plan = f"""
    - action: read
      params:
        source: "{test_url}"
    """

    # Act
    result = run_teddy_with_stdin(plan, cwd=Path("."))
    output = result.stdout
    print(f"\n--- TEDDY STDOUT ---\n{output}\n--- END TEDDY STDOUT ---")

    # Assert
    assert "Run Summary: FAILURE" in output
    assert f"### Action: `read` (`{test_url}`)" in output
    assert "status: FAILURE" in output
    assert "404 Client Error" in output
