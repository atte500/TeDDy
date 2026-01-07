from pathlib import Path
import yaml
from pytest_httpserver import HTTPServer

from .helpers import run_teddy_with_stdin


def test_read_local_file_successfully(tmp_path: Path):
    """
    Scenario 1: Read a local file successfully
    Given a file exists with known content,
    When the teddy executor is run with a plan to read the file,
    Then the execution report indicates success and contains the file's content.
    """
    # Arrange
    source_file = tmp_path / "source.txt"
    expected_content = "Hello, TeDDy!"
    source_file.write_text(expected_content)

    plan = f"""
    - action: read
      params:
        source: "{source_file}"
    """
    # Act
    result = run_teddy_with_stdin(plan, cwd=tmp_path)

    # Assert
    assert result.returncode == 0
    report = yaml.safe_load(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"
    assert action_log["output"] == expected_content


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

    # Assert
    assert result.returncode != 0
    report = yaml.safe_load(result.stdout)
    assert report["run_summary"]["status"] == "FAILURE"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "FAILURE"
    assert "No such file or directory" in action_log["error"]


def test_read_remote_url_successfully(httpserver: HTTPServer):
    """
    Scenario 3: Read a remote URL successfully
    Given a valid and accessible URL,
    When the teddy executor is run with a plan to read the URL,
    Then the execution report indicates success and contains the page content.
    """
    # Arrange
    html_content = "<h1>Test Header</h1><p>Test paragraph.</p>"
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

    # Assert
    assert result.returncode == 0
    report = yaml.safe_load(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"
    # The web scraper adapter converts HTML to markdown
    assert expected_markdown_content in action_log["output"]


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

    # Assert
    assert result.returncode != 0
    report = yaml.safe_load(result.stdout)
    assert report["run_summary"]["status"] == "FAILURE"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "FAILURE"
    assert "404 Client Error" in action_log["error"]
